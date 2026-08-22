"""
POST /api/tasks — Phase 1 implementation.

Creates a task record, calls the local LLM (via model registry),
updates the record to COMPLETED, and returns the full response.
"""
import logging
from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

from database.session import get_db
from database.models import Task
from models.registry import registry, TaskRequest, TaskResponse

logger = logging.getLogger(__name__)

router = APIRouter()


def create_task_record(db: Session, prompt: str) -> Task:
    """Insert a new Task row with status CREATED."""
    task = Task(description=prompt, status="CREATED")
    db.add(task)
    db.commit()
    db.refresh(task)
    logger.info("Task created: id=%s", task.id)
    return task


def update_task_record(db: Session, task: Task, model_used: str, response: str) -> Task:
    """Update an existing Task row to COMPLETED."""
    task.status = "COMPLETED"
    task.model_used = model_used
    task.response = response
    db.commit()
    db.refresh(task)
    logger.info("Task completed: id=%s model=%s", task.id, model_used)
    return task


@router.post("/tasks", response_model=TaskResponse)
def create_task(req: TaskRequest, db: Session = Depends(get_db)):
    # 1. Persist task with status CREATED
    task = create_task_record(db, req.prompt)

    # 2. Phase 2: Classify and Route
    task_type = registry.classify_task(req.prompt)
    model_id = registry.route_task(req.prompt)
    
    # Log the route decision to DB
    from database.repo import log_model_selection
    log_model_selection(
        db=db, 
        task_id=task.id, 
        task_type=task_type, 
        selected_model=model_id,
        routing_reason=f"Classification: {task_type}"
    )

    # 3. Call local model
    model_response, latency_ms = registry.execute_prompt(model_id, req.prompt)

    # 4. Persist completed task
    task = update_task_record(db, task, model_id, model_response)

    return TaskResponse(
        task_id=task.id,
        status=task.status,
        response=model_response,
        model_used=model_id,
        latency_ms=latency_ms,
    )

