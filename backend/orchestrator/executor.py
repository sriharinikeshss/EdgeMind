"""
Executor — Phase 0 scaffold (M1).

In Phase 3, execute_plan() will walk the DAG, call tools via the
Tool Registry, and push WS step events to the UI.
"""
from __future__ import annotations
from orchestrator.planner import ExecutionPlan, PlanStep


class Executor:
    """
    Walks an ExecutionPlan step-by-step, calling the Tool Registry for each step.

    Phase 1: not used (direct model call in tasks.py).
    Phase 3: full DAG-walking executor with retries and WS events.
    """

    def execute_plan(self, plan: ExecutionPlan) -> dict:
        """TODO Phase 3: walk the plan DAG and execute each step."""
        raise NotImplementedError("Executor wired in Phase 3.")

    def execute_step(self, step: PlanStep) -> dict:
        """TODO Phase 3: call Tool Registry for a single step."""
        raise NotImplementedError("Step execution wired in Phase 3.")

    def observe_tool_result(self, step: PlanStep, result: dict) -> None:
        """TODO Phase 3: feed tool output back into context for next steps."""
        raise NotImplementedError("Tool result observation wired in Phase 3.")

    def update_task_state(self, task_id: str, new_status: str) -> None:
        """TODO Phase 3: persist task state via TaskStateMachine."""
        raise NotImplementedError("Task state update wired in Phase 3.")

    def retry_step(self, step: PlanStep, reason: str) -> dict:
        """TODO Phase 4: retry a failed step with correction context."""
        raise NotImplementedError("Step retry wired in Phase 4.")
