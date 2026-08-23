"""
POST /api/agent — Phase 3 agent loop endpoint (M1).

Runs the full Planner → Executor → Validator loop for a task.
Returns the execution trace and final status.
"""
import json
import logging
from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session
from pydantic import BaseModel

from database.session import get_db
from database.models import Task, TaskStep
from orchestrator.planner import Planner
from orchestrator.executor import Executor
from orchestrator.validator import Validator
from orchestrator.state_machine import TaskStateMachine, TaskStatus
from database.repo import log_model_selection

logger = logging.getLogger(__name__)
router = APIRouter()

planner = Planner()
validator = Validator()

# Phase 8: bounded replan loop when execution succeeds but validation doesn't.
MAX_REPLAN_ATTEMPTS = 3
GROUNDING_THRESHOLD = 0.5


class AgentRequest(BaseModel):
    prompt: str
    expected_schema: dict | None = None   # optional output schema for validation
    image_base64: str | None = None       # Phase 5: optional attached scanned document/image
    filename: str | None = None


class StepResult(BaseModel):
    step_id: str | None = None
    action: str | None = None
    success: bool
    output: str | None = None
    error: str | None = None
    tool: str | None = None
    tool_data: dict | None = None


class AgentResponse(BaseModel):
    task_id: str
    status: str
    steps: list[StepResult]
    final_output: str
    validation_passed: bool
    events: list[dict]
    grounding_score: float = 1.0
    validation_report: dict | None = None
    retry_count: int = 0
    artifacts: list[dict] = []
    model_used: str | None = None


from api.auth import get_current_user, UserInfo

@router.post("/agent", response_model=AgentResponse)
def run_agent(req: AgentRequest, db: Session = Depends(get_db), current_user: UserInfo = Depends(get_current_user)):
    """
    Full Phase 3 agent loop:
    CREATED → CLASSIFIED → PLANNED → EXECUTING → VALIDATING → COMPLETED/FAILED
    """
    # 1. Create task record
    import uuid
    task_id = str(uuid.uuid4())
    task = Task(id=task_id, description=req.prompt, status=TaskStatus.CREATED.value)
    db.add(task)
    db.commit()
    db.refresh(task)

    sm = TaskStateMachine(task_id, TaskStatus.CREATED)

    try:
        # Phase 9 (M6): heuristic prompt-injection scan on the incoming request.
        # Not blocking (it's the authenticated user's own input, and false
        # positives would break legitimate prompts) — audited so a pattern of
        # injection attempts is visible in the sovereignty/audit trail.
        from security.prompt_injection import detect_prompt_injection
        injection_check = detect_prompt_injection(req.prompt)
        if injection_check["detected"]:
            from database.repo import log_audit_action
            log_audit_action(
                db=db, action="PROMPT_INJECTION_DETECTED", user_id=current_user.username,
                details=f"Task {task_id}: prompt matched heuristic(s) {injection_check['matches']}",
            )

        # 2. CLASSIFY
        sm.transition(TaskStatus.CLASSIFIED)
        sm.persist_task_state(db)
        task_type = planner.classify_task(req.prompt)

        # Decode image_base64 to file — convert PDFs to PNG so the vision tools
        # always receive a proper image, never raw PDF bytes.
        file_attachments = None
        if req.image_base64:
            import base64 as _b64
            import os
            os.makedirs("/app/data/workspaces", exist_ok=True)
            b64_data = req.image_base64
            if "," in b64_data:
                b64_data = b64_data.split(",", 1)[1]
            try:
                raw_bytes = _b64.b64decode(b64_data)

                # Detect file type by magic bytes — never trust the filename/extension
                is_pdf = raw_bytes[:4] == b"%PDF" or "application/pdf" in req.image_base64

                if is_pdf:
                    # Convert first page of PDF → PNG using PyMuPDF
                    try:
                        import fitz  # PyMuPDF
                        doc = fitz.open("pdf", raw_bytes)
                        page = doc.load_page(0)
                        pix = page.get_pixmap(dpi=200)
                        raw_bytes = pix.tobytes("png")
                        logger.info("Converted PDF attachment to PNG for task %s", task_id)
                    except ImportError:
                        logger.error("PyMuPDF not installed — cannot convert PDF attachment. "
                                     "Add pymupdf to requirements.txt")
                    except Exception as e:
                        logger.error("Failed to rasterize PDF attachment: %s", e)

                image_path = f"/app/data/workspaces/{task_id}_attached.png"
                with open(image_path, "wb") as f:
                    f.write(raw_bytes)
                file_attachments = [image_path]
            except Exception as e:
                logger.error("Failed to decode attached image: %s", e)

        # 3. PLAN (first attempt — replans happen inside the loop below)
        sm.transition(TaskStatus.PLANNED)
        sm.persist_task_state(db)

        # Log routing decision
        from models.registry import registry
        from database.repo import log_audit_action

        model_id = registry.route_task(req.prompt)
        log_model_selection(
            db=db,
            task_id=task_id,
            task_type=task_type,
            selected_model=model_id,
            routing_reason=f"Phase 3 agent loop classification: {task_type}",
        )

        log_audit_action(
            db=db,
            action="MODEL_ROUTE",
            details=f"Task {task_id} routed to {model_id} (Type: {task_type})"
        )

        # 4-6. EXECUTE → VALIDATE, with a bounded Phase 8 replan loop: if execution
        # succeeds but the answer fails grounding/schema validation, regenerate the
        # plan with the specific failure fed back in, up to MAX_REPLAN_ATTEMPTS times.
        # A hard execution failure (a step that exhausted its own Phase 3/4 tool-level
        # retries) is NOT eligible for replanning — the state machine is already
        # terminal (FAILED) at that point.
        plan = None
        all_events: list[dict] = []
        step_results: list[StepResult] = []
        final_output = ""
        claims: list[str] = []
        unsupported_claims: list[str] = []
        grounding_score = 1.0
        validation_passed = False
        retry_count = 0
        failure_reason = None
        execution_result = {"status": "FAILED", "results": [], "events": []}

        while True:
            plan = (
                planner.generate_plan(task_id, req.prompt, file_attachments=file_attachments)
                if plan is None
                else planner.replan(task_id, req.prompt, failure_reason=failure_reason, file_attachments=file_attachments)
            )

            sm.transition(TaskStatus.EXECUTING)
            sm.persist_task_state(db)
            executor = Executor(db_session=db, user_role=current_user.role, username=current_user.username)
            execution_result = executor.execute_plan(plan, sm)
            all_events.extend(executor.events)

            step_results = []
            for r in execution_result.get("results", []):
                step_results.append(StepResult(
                    step_id=None,
                    action=None,
                    success=r.get("success", False),
                    output=str(r.get("output", ""))[:2000],
                    error=r.get("error"),
                    tool=r.get("tool"),
                    tool_data=r.get("tool_data"),
                ))
            for step, sr in zip(plan.steps, step_results):
                sr.step_id = step.step_id
                sr.action = step.action

            final_output = "\n".join(str(r.output or "") for r in step_results if r.success)

            if execution_result["status"] != "COMPLETED":
                failed = next((r for r in execution_result.get("results", []) if not r.get("success")), None)
                failure_reason = f"Execution failed: {failed.get('error') if failed else 'unknown step failure'}"
                grounding_score = 0.0
                validation_passed = False
                break  # sm is already FAILED (set by the Executor) — not eligible for replanning

            sm.transition(TaskStatus.VALIDATING)
            sm.persist_task_state(db)

            # Phase 8: grounding score against whichever source-of-truth this plan used —
            # RAG citation text if a rag_search step ran, else the Phase 5 vision
            # extraction if a vision step ran, else there's nothing to hallucinate
            # against and the answer is trivially grounded.
            rag_text = "\n".join(r.output or "" for r in step_results if r.tool == "rag_search" and r.success)
            vision_extraction = next(
                (r.tool_data for r in step_results
                 if r.tool in ("analyze_scanned_document", "analyze_engineering_drawing") and r.tool_data),
                None,
            )
            # Claims come from the actual textual reasoning/summary step (skipping artifact
            # JSON receipts like {"status": "ok", "id": ...}) — so grounding is scored
            # on the synthesized analysis against the source-of-truth.
            from tools.registry import ARTIFACT_TOOL_NAMES
            non_artifact_outputs = [
                r.output for r in reversed(step_results)
                if r.success and r.tool not in ARTIFACT_TOOL_NAMES and r.output
            ]
            answer_text = non_artifact_outputs[0] if non_artifact_outputs else final_output
            claims = validator.extract_claims(answer_text)
            if rag_text:
                grounding_score = validator.calculate_grounding_score(claims, rag_text)
                unsupported_claims = validator.detect_unsupported_claims(claims, rag_text)
            elif vision_extraction:
                unsupported_claims = validator.detect_hallucination_risk(claims, vision_extraction)
                grounding_score = round(1.0 - (len(unsupported_claims) / len(claims)), 3) if claims else 1.0
            else:
                grounding_score, unsupported_claims = 1.0, []

            schema_ok = validator.validate_answer(task_id, final_output, req.expected_schema)
            grounding_ok = grounding_score >= GROUNDING_THRESHOLD
            validation_passed = schema_ok and grounding_ok

            if validation_passed:
                break

            failure_reason = (
                "Output was empty or did not match the expected schema."
                if not schema_ok
                else (
                    f"Grounding score {grounding_score} is below the {GROUNDING_THRESHOLD} threshold. "
                    f"Unsupported claims: {unsupported_claims[:3]}"
                )
            )

            retry_count += 1
            if retry_count > MAX_REPLAN_ATTEMPTS:
                log_audit_action(
                    db=db,
                    action="ESCALATED_TO_HUMAN_REVIEW",
                    details=f"Task {task_id} exhausted {MAX_REPLAN_ATTEMPTS} replan attempts. Last reason: {failure_reason}",
                )
                break

            logger.info("Task %s failed validation (attempt %d/%d) — replanning: %s",
                        task_id, retry_count, MAX_REPLAN_ATTEMPTS, failure_reason)
            sm.transition(TaskStatus.RETRYING)
            sm.persist_task_state(db)

        # 7. COMPLETE or FAIL based on the final attempt
        if validation_passed:
            sm.transition(TaskStatus.COMPLETED)
        elif sm.status != TaskStatus.FAILED:
            sm.transition(TaskStatus.FAILED)
        sm.persist_task_state(db)

        validation_report = {
            "claims": claims,
            "unsupported_claims": unsupported_claims,
            "grounding_score": grounding_score,
            "retry_count": retry_count,
            "escalated": retry_count > MAX_REPLAN_ATTEMPTS,
            "failure_reason": None if validation_passed else failure_reason,
        }

        # Update task record with final response
        task.response = final_output
        task.model_used = model_id
        task.grounding_score = grounding_score
        task.validation_report = json.dumps(validation_report)
        task.retry_count = retry_count
        db.commit()

        # Query any artifacts generated in this task
        from database.models import Artifact
        task_artifacts = db.query(Artifact).filter(Artifact.task_id == task_id).all()
        artifacts_list = [
            {
                "id": a.id,
                "filename": a.filename,
                "file_hash": a.file_hash,
                "content_type": a.content_type,
                "created_at": str(a.created_at),
            }
            for a in task_artifacts
        ]

        return AgentResponse(
            task_id=task_id,
            status=sm.status.value,
            steps=step_results,
            final_output=final_output,
            validation_passed=validation_passed,
            events=all_events,
            grounding_score=grounding_score,
            validation_report=validation_report,
            retry_count=retry_count,
            artifacts=artifacts_list,
            model_used=model_id,
        )

    except Exception as exc:
        logger.error("Agent loop failed for task %s: %s", task_id, exc)
        try:
            db.rollback()
            sm.transition(TaskStatus.FAILED)
            sm.persist_task_state(db)
        except Exception:
            pass
        return AgentResponse(
            task_id=task_id,
            status="FAILED",
            steps=[],
            final_output="",
            validation_passed=False,
            events=[{"type": "error", "message": str(exc)}],
        )
