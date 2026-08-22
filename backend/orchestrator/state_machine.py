"""
TaskStateMachine — Phase 3 full implementation (M1).

Implements state transitions persisted to the DB via persist_task_state()
and restore_task_state().
"""
from __future__ import annotations
from enum import Enum
import logging

logger = logging.getLogger(__name__)


class TaskStatus(str, Enum):
    CREATED = "CREATED"
    CLASSIFIED = "CLASSIFIED"
    PLANNED = "PLANNED"
    EXECUTING = "EXECUTING"
    VALIDATING = "VALIDATING"
    RETRYING = "RETRYING"
    COMPLETED = "COMPLETED"
    FAILED = "FAILED"


# Valid transitions: from_state → set of allowed to_states
_TRANSITIONS: dict[TaskStatus, set[TaskStatus]] = {
    TaskStatus.CREATED:    {TaskStatus.CLASSIFIED, TaskStatus.FAILED},
    TaskStatus.CLASSIFIED: {TaskStatus.PLANNED, TaskStatus.FAILED},
    TaskStatus.PLANNED:    {TaskStatus.EXECUTING, TaskStatus.FAILED},
    TaskStatus.EXECUTING:  {TaskStatus.VALIDATING, TaskStatus.RETRYING, TaskStatus.FAILED},
    TaskStatus.VALIDATING: {TaskStatus.COMPLETED, TaskStatus.RETRYING, TaskStatus.FAILED},
    TaskStatus.RETRYING:   {TaskStatus.EXECUTING, TaskStatus.FAILED},
    TaskStatus.COMPLETED:  set(),
    TaskStatus.FAILED:     set(),
}


class TaskStateMachine:
    """
    Lightweight in-memory state machine for a single task with DB persistence.
    """

    def __init__(self, task_id: str, initial_status: TaskStatus = TaskStatus.CREATED):
        self.task_id = task_id
        self._status = initial_status

    @property
    def status(self) -> TaskStatus:
        return self._status

    def transition(self, new_status: TaskStatus) -> None:
        """
        Attempt a state transition.
        Raises ValueError if the transition is not allowed.
        """
        allowed = _TRANSITIONS.get(self._status, set())
        if new_status not in allowed:
            raise ValueError(
                f"Illegal transition for task {self.task_id}: "
                f"{self._status} → {new_status}. "
                f"Allowed: {allowed}"
            )
        old_status = self._status
        self._status = new_status
        logger.info("Task %s: %s → %s", self.task_id, old_status, new_status)

    def persist_task_state(self, db_session) -> None:
        """Phase 3: write current status to the tasks table."""
        from database.models import Task
        task = db_session.query(Task).filter(Task.id == self.task_id).first()
        if task:
            task.status = self._status.value
            db_session.commit()
            logger.debug("Persisted task %s state: %s", self.task_id, self._status)

    def restore_task_state(self, db_session) -> None:
        """Phase 3: load status from the tasks table."""
        from database.models import Task
        task = db_session.query(Task).filter(Task.id == self.task_id).first()
        if task:
            self._status = TaskStatus(task.status)
            logger.debug("Restored task %s state: %s", self.task_id, self._status)

    def __repr__(self) -> str:
        return f"<TaskStateMachine task={self.task_id} status={self._status}>"
