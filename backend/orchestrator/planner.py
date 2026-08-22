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
    Phase 2: adds rule-based classify_task() to feed the router.
    Phase 3: full LLM-driven decomposition via generate_plan().
    """

    def classify_task(self, description: str) -> str:
        """
        Phase 2: Simple heuristic/keyword classifier.
        Returns the generic task type: 'CODING', 'VISION', 'RAG', or 'REASONING'.
        """
        desc_lower = description.lower()
        if any(kw in desc_lower for kw in ["code", "python", "script", "function", "debug", "sql", "query", "react", "regex", "java"]):
            return "CODING"
        if any(kw in desc_lower for kw in ["image", "photo", "scan", "ocr", "picture"]):
            return "VISION"
        if any(kw in desc_lower for kw in ["sop", "manual", "document", "retrieve"]):
            return "RAG"
        return "REASONING"

    def generate_plan(self, task_id: str, description: str) -> ExecutionPlan:
        """TODO Phase 3: call reasoning model to produce a structured step plan."""
        raise NotImplementedError("Full planner implemented in Phase 3.")

    def decompose_task(self, description: str) -> list[str]:
        """TODO Phase 3: break a task into a list of sub-task descriptions."""
        raise NotImplementedError("Task decomposition implemented in Phase 3.")

    def create_execution_graph(self, steps: list[PlanStep]) -> ExecutionPlan:
        """TODO Phase 3: topologically sort steps into an executable DAG."""
        raise NotImplementedError("Execution graph builder implemented in Phase 3.")
