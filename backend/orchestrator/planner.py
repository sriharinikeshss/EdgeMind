"""
Planner — Phase 0 scaffold (M1).

In Phase 3, generate_plan() will call the reasoning model with a
"produce a JSON step plan" prompt and parse the result into a DAG.
"""
from __future__ import annotations
from dataclasses import dataclass, field
from typing import Any


@dataclass
class PlanStep:
    step_id: str
    action: str
    tool: str | None = None
    depends_on: list[str] = field(default_factory=list)
    params: dict[str, Any] = field(default_factory=dict)


@dataclass
class ExecutionPlan:
    task_id: str
    steps: list[PlanStep] = field(default_factory=list)


class Planner:
    """
    Converts a task description into an ExecutionPlan (DAG of steps).

    Phase 1: trivial single-step plan (direct model call, no tools).
    Phase 3: full LLM-driven decomposition via generate_plan().
    """

    def generate_plan(self, task_id: str, description: str) -> ExecutionPlan:
        """TODO Phase 3: call reasoning model to produce a structured step plan."""
        raise NotImplementedError("Full planner implemented in Phase 3.")

    def decompose_task(self, description: str) -> list[str]:
        """TODO Phase 3: break a task into a list of sub-task descriptions."""
        raise NotImplementedError("Task decomposition implemented in Phase 3.")

    def create_execution_graph(self, steps: list[PlanStep]) -> ExecutionPlan:
        """TODO Phase 3: topologically sort steps into an executable DAG."""
        raise NotImplementedError("Execution graph builder implemented in Phase 3.")
