"""
Planner — Phase 3 implementation (M1).

generate_plan() calls the reasoning model with a structured prompt,
parses the JSON plan response into a DAG of PlanSteps.
decompose_task() breaks a description into sub-tasks.
create_execution_graph() topologically orders steps.
"""
from __future__ import annotations
import json
import uuid
import logging
from dataclasses import dataclass, field
from typing import Any

logger = logging.getLogger(__name__)


@dataclass
class PlanStep:
    step_id: str
    action: str
    tool: str | None = None
    depends_on: list[str] = field(default_factory=list)
    params: dict[str, Any] = field(default_factory=dict)
    status: str = "PENDING"   # PENDING | RUNNING | DONE | FAILED


@dataclass
class ExecutionPlan:
    task_id: str
    steps: list[PlanStep] = field(default_factory=list)


# System prompt used to instruct the reasoning model to produce a structured plan
_PLAN_SYSTEM_PROMPT = """
You are a task planner. Given a user task description, produce a JSON execution plan.
The plan must be a JSON object with a key "steps" containing a list of step objects.
Each step object must have:
  - "step_id": a short unique ID like "step_1"
  - "action": a brief description of what to do
  - "tool": tool to use. Available options:
      * "direct_llm": Use for summarization, checklists, reasoning, writing, and text analysis (Default for most steps).
      * "execute_python": Use ONLY if the step requires executing actual Python code or calculations.
      * "rag_search": Use ONLY if searching stored SOPs, manuals, or documents.
      * "run_ocr": Use ONLY if reading scanned document images or PDFs.
  - "depends_on": list of step_ids this step depends on (can be empty list)
  - "params": dict of parameters for the tool call (can be empty dict)

Only output valid JSON, no extra text.
Example:
{
  "steps": [
    {"step_id": "step_1", "action": "Summarize the key points", "tool": "direct_llm", "depends_on": [], "params": {}},
    {"step_id": "step_2", "action": "Convert summary into a checklist", "tool": "direct_llm", "depends_on": ["step_1"], "params": {}}
  ]
}
"""


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
        """
        Phase 3: call reasoning model to produce a structured step plan.
        Parses the JSON into a DAG of PlanSteps.
        Falls back to a single-step direct_llm plan if model is unavailable.
        """
        from models.registry import registry

        prompt = (
            f"{_PLAN_SYSTEM_PROMPT}\n\nUser task:\n{description}"
        )
        model_id = registry.route_task(description)

        try:
            response_text, _ = registry.execute_prompt(model_id, prompt)
            # Strip markdown code fences if present
            cleaned = response_text.strip()
            if cleaned.startswith("```"):
                cleaned = "\n".join(cleaned.split("\n")[1:])
                if cleaned.endswith("```"):
                    cleaned = cleaned[:-3].strip()

            plan_data = json.loads(cleaned)
            steps = [
                PlanStep(
                    step_id=s.get("step_id", f"step_{i}"),
                    action=s.get("action", ""),
                    tool=s.get("tool"),
                    depends_on=s.get("depends_on", []),
                    params=s.get("params", {}),
                )
                for i, s in enumerate(plan_data.get("steps", []))
            ]
            if not steps:
                raise ValueError("Empty steps list from model")
        except Exception as exc:
            logger.warning("Plan generation failed (%s). Using single-step fallback.", exc)
            steps = [
                PlanStep(
                    step_id="step_1",
                    action=description,
                    tool="direct_llm",
                    depends_on=[],
                    params={"prompt": description},
                )
            ]

        return ExecutionPlan(task_id=task_id, steps=steps)

    def decompose_task(self, description: str) -> list[str]:
        """
        Phase 3: break a task into a list of sub-task descriptions
        using the LLM. Falls back to [description] on error.
        """
        from models.registry import registry
        model_id = registry.route_task(description)
        prompt = (
            f"Break the following task into 2-5 concise sub-tasks. "
            f"Output them as a JSON list of strings.\nTask: {description}"
        )
        try:
            response_text, _ = registry.execute_prompt(model_id, prompt)
            cleaned = response_text.strip().strip("```json").strip("```")
            sub_tasks = json.loads(cleaned)
            if isinstance(sub_tasks, list) and sub_tasks:
                return sub_tasks
        except Exception as exc:
            logger.warning("decompose_task failed (%s). Returning original.", exc)
        return [description]

    def create_execution_graph(self, steps: list[PlanStep]) -> ExecutionPlan:
        """
        Phase 3: topologically sort steps into an executable DAG.
        Uses Kahn's algorithm.
        """
        task_id = str(uuid.uuid4())
        # Build adjacency and in-degree maps
        step_map = {s.step_id: s for s in steps}
        in_degree = {s.step_id: 0 for s in steps}
        for step in steps:
            for dep in step.depends_on:
                if dep in in_degree:
                    in_degree[step.step_id] += 1

        # Kahn's BFS topological sort
        queue = [sid for sid, deg in in_degree.items() if deg == 0]
        sorted_steps: list[PlanStep] = []
        visited: set[str] = set()

        while queue:
            current_id = queue.pop(0)
            if current_id in visited:
                continue
            visited.add(current_id)
            sorted_steps.append(step_map[current_id])
            # Reduce in-degree of dependents
            for step in steps:
                if current_id in step.depends_on:
                    in_degree[step.step_id] -= 1
                    if in_degree[step.step_id] == 0:
                        queue.append(step.step_id)

        # Append any steps not yet visited (safety fallback)
        for step in steps:
            if step.step_id not in visited:
                sorted_steps.append(step)

        return ExecutionPlan(task_id=task_id, steps=sorted_steps)
