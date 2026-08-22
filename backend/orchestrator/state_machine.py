"""
TaskStateMachine — Phase 0 scaffold (M1).

Implements the state enum and transition rules from the architecture doc.
The actual state-machine logic (persisting state, running transitions) will
be fleshed out in Phase 3. For now, this gives all team members the shared
vocabulary so the codebase compiles cleanly.
"""
from enum import Enum


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
    TaskStatus.CREATED: {TaskStatus.CLASSIFIED, TaskStatus.FAILED},
    TaskStatus.CLASSIFIED: {TaskStatus.PLANNED, TaskStatus.FAILED},
    TaskStatus.PLANNED: {TaskStatus.EXECUTING, TaskStatus.FAILED},
    TaskStatus.EXECUTING: {TaskStatus.VALIDATING, TaskStatus.RETRYING, TaskStatus.FAILED},
    TaskStatus.VALIDATING: {TaskStatus.COMPLETED, TaskStatus.RETRYING, TaskStatus.FAILED},
    TaskStatus.RETRYING: {TaskStatus.EXECUTING, TaskStatus.FAILED},
    TaskStatus.COMPLETED: set(),
    TaskStatus.FAILED: set(),
}


class TaskStateMachine:
    """
    Lightweight in-memory state machine for a single task.
    Phase 3 will add DB persistence via persist_task_state() / restore_task_state().
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
        self._status = new_status

    def persist_task_state(self, db_session) -> None:
        """TODO Phase 3: write current status to the tasks table."""
        raise NotImplementedError("State persistence wired in Phase 3.")

    def restore_task_state(self, db_session) -> None:
        """TODO Phase 3: load status from the tasks table."""
        raise NotImplementedError("State restoration wired in Phase 3.")

    def __repr__(self) -> str:
        return f"<TaskStateMachine task={self.task_id} status={self._status}>"
