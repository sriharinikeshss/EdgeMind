"""
POST /api/agent — Phase 3 agent loop endpoint (M1).

Runs the full Planner → Executor → Validator loop for a task.
Returns the execution trace and final status.
"""
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
        # 2. CLASSIFY
        sm.transition(TaskStatus.CLASSIFIED)
        sm.persist_task_state(db)
        task_type = planner.classify_task(req.prompt)

        # Decode image_base64 to file
        file_attachments = None
        if req.image_base64:
            import base64
            import os
            os.makedirs("/app/data/workspaces", exist_ok=True)
            image_path = f"/app/data/workspaces/{task_id}_attached.png"
            b64_data = req.image_base64
            if "," in b64_data:
                b64_data = b64_data.split(",")[1]
            try:
                with open(image_path, "wb") as f:
                    f.write(base64.b64decode(b64_data))
                file_attachments = [image_path]
            except Exception as e:
                logger.error("Failed to decode attached image: %s", e)

        # 3. PLAN
        sm.transition(TaskStatus.PLANNED)
        sm.persist_task_state(db)
        plan = planner.generate_plan(task_id, req.prompt, file_attachments=file_attachments)

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

        # 4. EXECUTE
        sm.transition(TaskStatus.EXECUTING)
        sm.persist_task_state(db)
        executor = Executor(db_session=db, user_role=current_user.role, username=current_user.username)
        execution_result = executor.execute_plan(plan, sm)

        # Collect step results
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
        for i, (step, sr) in enumerate(zip(plan.steps, step_results)):
            sr.step_id = step.step_id
            sr.action = step.action

        # 5. VALIDATE
        final_output = "\n".join(
            str(r.output or "") for r in step_results if r.success
        )
        validation_passed = False
        if execution_result["status"] == "COMPLETED":
            sm.transition(TaskStatus.VALIDATING)
            sm.persist_task_state(db)
            validation_passed = validator.validate_answer(task_id, final_output, req.expected_schema)

        # 6. COMPLETE or FAIL based on execution + validation
        if execution_result["status"] == "COMPLETED" and validation_passed:
            sm.transition(TaskStatus.COMPLETED)
        elif sm.status != TaskStatus.FAILED:
            sm.transition(TaskStatus.FAILED)
        sm.persist_task_state(db)

        # Update task record with final response
        task.response = final_output
        task.model_used = model_id
        db.commit()

        return AgentResponse(
            task_id=task_id,
            status=sm.status.value,
            steps=step_results,
            final_output=final_output,
            validation_passed=validation_passed,
            events=executor.events,
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
