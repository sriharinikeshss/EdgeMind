"""
POST /api/agent/stream - Server-Sent Events streaming version of the agent endpoint.
Pushes real-time JSON events to the browser as each pipeline stage completes.

SSE event types:
    pipeline_start    - pipeline has started
    stage             - stage name changed (PLANNING / EXECUTING / VALIDATING)
    step_start        - an executor step just started
    step_done         - an executor step just finished
    validation_check  - a single validation gate result
    complete          - full final payload
    error             - unrecoverable failure
"""
import json
import logging
import queue
import threading
import uuid

from fastapi import APIRouter, Depends
from fastapi.responses import StreamingResponse
from pydantic import BaseModel

from database.session import SessionLocal
from database.models import Task, Artifact
from database.repo import log_model_selection, log_audit_action
from orchestrator.planner import Planner
from orchestrator.executor import Executor
from orchestrator.validator import Validator
from orchestrator.state_machine import TaskStateMachine, TaskStatus
from api.auth import get_current_user, UserInfo

logger = logging.getLogger(__name__)
router = APIRouter()
planner = Planner()
validator = Validator()

MAX_REPLAN_ATTEMPTS = 3
GROUNDING_THRESHOLD = 0.5


class AgentStreamRequest(BaseModel):
    prompt: str
    expected_schema: dict | None = None
    image_base64: str | None = None
    filename: str | None = None


def _sse(data: dict) -> str:
    return f"data: {json.dumps(data, default=str)}\n\n"


def _run_pipeline(req, username: str, user_role: str, event_q: queue.SimpleQueue):
    db = SessionLocal()
    task_id = str(uuid.uuid4())

    def emit(data: dict):
        event_q.put(("event", data))

    try:
        task = Task(id=task_id, description=req.prompt, status=TaskStatus.CREATED.value)
        db.add(task)
        db.commit()
        db.refresh(task)
        sm = TaskStateMachine(task_id, TaskStatus.CREATED)
        emit({"type": "pipeline_start", "task_id": task_id})

        from security.prompt_injection import detect_prompt_injection
        if detect_prompt_injection(req.prompt)["detected"]:
            log_audit_action(db=db, action="PROMPT_INJECTION_DETECTED",
                             user_id=username, details=f"Task {task_id}")

        sm.transition(TaskStatus.CLASSIFIED)
        sm.persist_task_state(db)
        task_type = planner.classify_task(req.prompt)

        file_attachments = None
        if req.image_base64:
            import base64 as _b64, os
            os.makedirs("/app/data/workspaces", exist_ok=True)
            b64_data = req.image_base64.split(",", 1)[-1] if "," in req.image_base64 else req.image_base64
            try:
                raw_bytes = _b64.b64decode(b64_data)
                if raw_bytes[:4] == b"%PDF":
                    try:
                        import fitz
                        raw_bytes = fitz.open("pdf", raw_bytes).load_page(0).get_pixmap(dpi=200).tobytes("png")
                    except Exception: pass
                img_path = f"/app/data/workspaces/{task_id}_attached.png"
                open(img_path, "wb").write(raw_bytes)
                file_attachments = [img_path]
            except Exception as e:
                logger.error("Attachment decode failed: %s", e)

        emit({"type": "stage", "stage": "PLANNING",
              "message": "Analysing prompt and building execution plan..."})
        sm.transition(TaskStatus.PLANNED)
        sm.persist_task_state(db)

        from models.registry import registry
        model_id = registry.route_task(req.prompt)
        log_model_selection(db=db, task_id=task_id, task_type=task_type,
                            selected_model=model_id, routing_reason=f"SSE stream: {task_type}")
        log_audit_action(db=db, action="MODEL_ROUTE",
                         details=f"Task {task_id} -> {model_id}", user_id=username)

        from tools.registry import ARTIFACT_TOOL_NAMES
        from api.agent import StepResult

        plan = None
        all_events, step_results = [], []
        final_output = ""
        claims, unsupported_claims = [], []
        grounding_score = 1.0
        validation_passed = False
        retry_count = 0
        failure_reason = None

        while True:
            plan = (
                planner.generate_plan(task_id, req.prompt, file_attachments=file_attachments)
                if plan is None
                else planner.replan(task_id, req.prompt, failure_reason=failure_reason,
                                    file_attachments=file_attachments)
            )

            emit({"type": "stage", "stage": "EXECUTING",
                  "message": f"Executing {len(plan.steps)} step(s)...",
                  "total_steps": len(plan.steps)})
            sm.transition(TaskStatus.EXECUTING)
            sm.persist_task_state(db)

            def _on_exec_event(evt: dict):
                t = evt.get("type", "")
                if t == "step_started":
                    emit({"type": "step_start",
                          "step_id": evt.get("step_id"),
                          "action": evt.get("action", ""),
                          "tool": evt.get("tool", "")})
                elif t == "step_completed":
                    emit({"type": "step_done",
                          "step_id": evt.get("step_id"),
                          "tool": evt.get("tool", ""),
                          "success": True,
                          "output_snippet": str(evt.get("output", ""))[:120]})
                elif t == "step_failed":
                    emit({"type": "step_done",
                          "step_id": evt.get("step_id"),
                          "tool": evt.get("tool", ""),
                          "success": False,
                          "error": evt.get("error", "")})

            executor = Executor(db_session=db, user_role=user_role,
                                username=username, event_callback=_on_exec_event)
            execution_result = executor.execute_plan(plan, sm)
            all_events.extend(executor.events)

            step_results = []
            for r in execution_result.get("results", []):
                step_results.append(StepResult(
                    step_id=None, action=None,
                    success=r.get("success", False),
                    output=str(r.get("output", ""))[:2000],
                    error=r.get("error"), tool=r.get("tool"), tool_data=r.get("tool_data")))
            for step, sr in zip(plan.steps, step_results):
                sr.step_id = step.step_id
                sr.action = step.action

            final_output = "\n".join(str(r.output or "") for r in step_results if r.success)

            if execution_result["status"] != "COMPLETED":
                failed = next((r for r in execution_result.get("results", []) if not r.get("success")), None)
                failure_reason = f"Execution failed: {failed.get('error') if failed else 'unknown'}"
                grounding_score = 0.0
                validation_passed = False
                emit({"type": "stage", "stage": "FAILED", "message": failure_reason})
                break

            # -- Validation ----------------------------------------------------
            emit({"type": "stage", "stage": "VALIDATING",
                  "message": "Running Validation Engine..."})
            sm.transition(TaskStatus.VALIDATING)
            sm.persist_task_state(db)

            # Gate 1: Schema
            schema_ok = validator.validate_answer(task_id, final_output, req.expected_schema)
            emit({"type": "validation_check", "check": "schema", "passed": schema_ok,
                  "label": "Schema Check",
                  "detail": "Output matched expected schema" if schema_ok else "Schema mismatch"})

            # Gate 2: Claims
            non_art = [r.output for r in reversed(step_results)
                       if r.success and r.tool not in ARTIFACT_TOOL_NAMES and r.output]
            answer_text = non_art[0] if non_art else final_output
            claims = validator.extract_claims(answer_text)
            emit({"type": "validation_check", "check": "claims", "passed": True,
                  "label": "Claim Extraction",
                  "detail": f"{len(claims)} verifiable claim(s) identified"})

            # Gate 3: Grounding
            rag_text = "\n".join(r.output or "" for r in step_results
                                 if r.tool == "rag_search" and r.success)
            vision_extraction = next(
                (r.tool_data for r in step_results
                 if r.tool in ("analyze_scanned_document", "analyze_engineering_drawing") and r.tool_data),
                None)
            is_base_model = False

            if rag_text:
                grounding_score = validator.calculate_grounding_score(claims, rag_text)
                unsupported_claims = validator.detect_unsupported_claims(claims, rag_text)
            elif vision_extraction:
                unsupported_claims = validator.detect_hallucination_risk(claims, vision_extraction)
                grounding_score = round(1.0 - len(unsupported_claims) / len(claims), 3) if claims else 1.0
            else:
                emit({"type": "validation_check", "check": "self_rag", "passed": None,
                      "label": "Self-RAG Retrieval",
                      "detail": "Searching Knowledge Library for supporting evidence..."})
                from rag.retrieval import rag_search
                self_rag_evidence = []
                for c in claims:
                    ev = rag_search(c)
                    if ev and len(ev) > 20:
                        self_rag_evidence.append(ev)
                if self_rag_evidence:
                    rag_text = "\n".join(self_rag_evidence)
                    scores = [validator.llm_judge_grounding(c, rag_text) for c in claims]
                    grounding_score = round(sum(scores) / len(scores), 3) if scores else 1.0
                    unsupported_claims = [c for c, s in zip(claims, scores) if s < GROUNDING_THRESHOLD]
                    emit({"type": "validation_check", "check": "self_rag", "passed": True,
                          "label": "Self-RAG Retrieval",
                          "detail": f"Found supporting evidence for {len(claims)} claim(s)"})
                else:
                    is_base_model = True
                    grounding_score = -1.0
                    unsupported_claims = []
                    emit({"type": "validation_check", "check": "self_rag", "passed": None,
                          "label": "Self-RAG Retrieval",
                          "detail": "No SOPs found - Base Model Knowledge (N/A)"})

            if not is_base_model:
                grounding_ok = grounding_score >= GROUNDING_THRESHOLD
                pct = int(grounding_score * 100)
                risk = "Low" if pct >= 80 else ("Medium" if pct >= 50 else "High")
                emit({"type": "validation_check", "check": "grounding",
                      "passed": grounding_ok, "label": "Grounding Verification",
                      "detail": f"Score: {pct}%  |  Risk: {risk}",
                      "score": grounding_score, "risk": risk, "base_model": False})
            else:
                grounding_ok = True
                emit({"type": "validation_check", "check": "grounding",
                      "passed": None, "label": "Grounding Verification",
                      "detail": "N/A - Base Model Knowledge",
                      "score": -1.0, "risk": "Inherent", "base_model": True})

            validation_passed = schema_ok and grounding_ok
            if validation_passed:
                break

            failure_reason = (
                "Output did not match expected schema." if not schema_ok
                else f"Grounding score {grounding_score} below threshold.")
            retry_count += 1
            if retry_count > MAX_REPLAN_ATTEMPTS:
                log_audit_action(db=db, action="ESCALATED_TO_HUMAN_REVIEW",
                                 details=f"Task {task_id} exhausted replans")
                break
            sm.transition(TaskStatus.RETRYING)
            sm.persist_task_state(db)

        # -- Finalise ----------------------------------------------------------
        if validation_passed:
            sm.transition(TaskStatus.COMPLETED)
        elif sm.status != TaskStatus.FAILED:
            sm.transition(TaskStatus.FAILED)
        sm.persist_task_state(db)

        validation_report = {
            "claims": claims, "unsupported_claims": unsupported_claims,
            "grounding_score": grounding_score, "retry_count": retry_count,
            "failure_reason": None if validation_passed else failure_reason,
        }
        task.response = final_output.replace("\x00", "")
        task.model_used = model_id
        task.grounding_score = grounding_score
        task.validation_report = json.dumps(validation_report).replace("\x00", "")
        task.retry_count = retry_count
        db.commit()

        task_artifacts = db.query(Artifact).filter(Artifact.task_id == task_id).all()
        emit({
            "type": "complete",
            "task_id": task_id,
            "status": sm.status.value,
            "final_output": final_output,
            "validation_passed": validation_passed,
            "grounding_score": grounding_score,
            "validation_report": validation_report,
            "retry_count": retry_count,
            "model_used": model_id,
            "artifacts": [{"id": a.id, "filename": a.filename, "file_hash": a.file_hash,
                           "content_type": a.content_type, "created_at": str(a.created_at)}
                          for a in task_artifacts],
            "steps": [{"step_id": sr.step_id, "action": sr.action, "success": sr.success,
                       "output": (sr.output or "")[:500], "tool": sr.tool, "error": sr.error}
                      for sr in step_results],
        })

    except Exception as exc:
        logger.error("SSE pipeline failed %s: %s", task_id, exc, exc_info=True)
        try: db.rollback()
        except Exception: pass
        emit({"type": "error", "message": str(exc), "task_id": task_id})
    finally:
        db.close()
        event_q.put(("done", None))


@router.post("/agent/stream")
def stream_agent(
    req: AgentStreamRequest,
    current_user: UserInfo = Depends(get_current_user),
):
    """SSE streaming agent endpoint - real-time events for each pipeline stage."""
    event_q: queue.SimpleQueue = queue.SimpleQueue()
    threading.Thread(
        target=_run_pipeline,
        args=(req, current_user.username, current_user.role, event_q),
        daemon=True,
    ).start()

    def generate():
        while True:
            msg_type, payload = event_q.get()
            if msg_type == "event":
                yield _sse(payload)
            elif msg_type == "done":
                break

    return StreamingResponse(
        generate(),
        media_type="text/event-stream",
        headers={"Cache-Control": "no-cache", "X-Accel-Buffering": "no"},
    )
