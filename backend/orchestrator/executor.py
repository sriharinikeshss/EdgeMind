"""
Executor — Phase 3 full implementation (M1).

execute_plan() walks the DAG of PlanSteps, calling tools via the ToolRegistry,
persisting each step result to task_steps, and emitting WS-ready status events.
"""
from __future__ import annotations
import json
import logging
from typing import Any

from orchestrator.planner import ExecutionPlan, PlanStep
from orchestrator.state_machine import TaskStateMachine, TaskStatus

logger = logging.getLogger(__name__)

MAX_RETRIES = 3


class Executor:
    """
    Walks an ExecutionPlan step-by-step, calling the Tool Registry for each step.
    Emits step events into an `events` list that can be streamed via WebSocket.
    """

    def __init__(self, db_session=None, user_role: str = "operator"):
        self.db = db_session
        self.user_role = user_role
        self.events: list[dict] = []   # collected step events for WS streaming
        self.context: dict[str, Any] = {}  # accumulates tool outputs across steps

    def _emit(self, event_type: str, payload: dict) -> None:
        event = {"type": event_type, **payload}
        self.events.append(event)
        logger.info("AGENT EVENT: %s", event)

    def execute_plan(self, plan: ExecutionPlan, sm: TaskStateMachine | None = None) -> dict:
        """
        Phase 3: Walk the plan DAG and execute each step.
        Returns {"status": "COMPLETED"|"FAILED", "results": [...], "events": [...]}
        """
        from tools.registry import tool_registry

        results = []
        sm = sm or TaskStateMachine(plan.task_id)

        self._emit("plan_started", {"task_id": plan.task_id, "total_steps": len(plan.steps)})

        # Track which steps are done so we only run a step when its deps are met
        completed_step_ids: set[str] = set()

        for step in plan.steps:
            # Wait for dependencies (plan is already topologically sorted)
            unmet = [dep for dep in step.depends_on if dep not in completed_step_ids]
            if unmet:
                logger.warning("Step %s skipped — unmet dependencies: %s", step.step_id, unmet)
                continue

            step.status = "RUNNING"
            self._emit("step_started", {"step_id": step.step_id, "action": step.action, "tool": step.tool})

            step_result = self._execute_step_with_retry(step, tool_registry, sm=sm)
            results.append(step_result)

            if step_result.get("success"):
                step.status = "DONE"
                completed_step_ids.add(step.step_id)
                # Store output in context for downstream steps
                self.context[step.step_id] = step_result.get("output", "")
                self._emit("step_completed", {"step_id": step.step_id, "output": str(step_result.get("output", ""))[:500]})
                self._write_step_to_db(plan.task_id, step, step_result)
            else:
                step.status = "FAILED"
                self._emit("step_failed", {"step_id": step.step_id, "error": step_result.get("error", "unknown")})
                self._write_step_to_db(plan.task_id, step, step_result)
                # DoD: a step that exhausts all retries must transition RETRYING → FAILED
                # before the plan is reported failed.
                self._fail_state_machine(sm)
                # If a step fails completely, fail the whole plan
                self._emit("plan_failed", {"task_id": plan.task_id, "failed_step": step.step_id})
                return {"status": "FAILED", "results": results, "events": self.events}

        self._emit("plan_completed", {"task_id": plan.task_id})
        return {"status": "COMPLETED", "results": results, "events": self.events}

    def _execute_step_with_retry(
        self, step: PlanStep, tool_registry, sm: TaskStateMachine | None = None, retries: int = MAX_RETRIES
    ) -> dict:
        """Execute a step, retrying up to MAX_RETRIES on failure.

        DoD: a failed attempt (with retries remaining) must drive the task
        state machine through RETRYING → EXECUTING for the next attempt —
        not just emit a log event — so the transition is real and persisted.
        """
        for attempt in range(1, retries + 1):
            t_id = sm.task_id if sm else "unknown"
            result = self.execute_step(step, tool_registry, task_id=t_id)
            if result.get("success"):
                return result
            logger.warning("Step %s attempt %d/%d failed: %s", step.step_id, attempt, retries, result.get("error"))
            if attempt < retries:
                self._transition_safely(sm, TaskStatus.RETRYING)
                self._emit("step_retrying", {"step_id": step.step_id, "attempt": attempt, "error": result.get("error")})
                self._transition_safely(sm, TaskStatus.EXECUTING)
        return result  # return last failure

    def _transition_safely(self, sm: TaskStateMachine | None, new_status: TaskStatus) -> None:
        """Attempt a state transition, persist it, and swallow illegal-transition
        errors (e.g. when a caller passes no sm or a mock/standalone state)."""
        if sm is None:
            return
        try:
            sm.transition(new_status)
            if self.db:
                sm.persist_task_state(self.db)
        except ValueError as exc:
            logger.debug("Skipped state transition to %s: %s", new_status, exc)

    def _fail_state_machine(self, sm: TaskStateMachine | None) -> None:
        """Drive the state machine to FAILED, passing through RETRYING first
        per the Phase 3 DoD ('a forced tool failure correctly transitions to
        RETRYING then FAILED')."""
        if sm is None:
            return
        if sm.status != TaskStatus.RETRYING:
            self._transition_safely(sm, TaskStatus.RETRYING)
        self._transition_safely(sm, TaskStatus.FAILED)

    def execute_step(self, step: PlanStep, tool_registry=None, task_id: str = "unknown") -> dict:
        """
        Phase 3: call Tool Registry for a single step.
        """
        from tools.registry import tool_registry as default_registry
        from models.registry import registry as model_registry

        registry = tool_registry or default_registry
        tool_name = step.tool or "direct_llm"

        # Inject context from previous steps into params
        params = {**step.params, "task_id": task_id}
        
        # Build context string from previous step outputs
        ctx_str = "\n".join(
            f"[{sid}]: {out}" for sid, out in self.context.items()
        )
        
        if "prompt" not in params and step.action:
            params["prompt"] = f"{step.action}\n\nContext from previous steps:\n{ctx_str}" if ctx_str else step.action
        elif "prompt" in params and ctx_str:
            params["prompt"] = f"{params['prompt']}\n\nContext from previous steps:\n{ctx_str}"

        try:
            if tool_name == "direct_llm":
                prompt = params.get("prompt", step.action)
                model_id = model_registry.route_task(prompt)
                output, _ = model_registry.execute_prompt(model_id, prompt)
                return {"success": True, "output": output, "tool": tool_name}

            if registry and tool_name in registry.list_tools():
                output = registry.execute_tool(tool_name, user_role=self.user_role, arguments=params, db=self.db)
                tool_data = None
                if isinstance(output, dict):
                    tool_data = output
                    if output.get("grounding_prompt"):
                        clean_output = output["grounding_prompt"]
                    elif output.get("stdout") is not None:
                        clean_output = output["stdout"]
                    else:
                        import json
                        clean_output = json.dumps(output)
                else:
                    clean_output = output
                return {"success": True, "output": clean_output, "tool": tool_name, "tool_data": tool_data}
            else:
                # Tool not registered yet — use direct_llm as fallback
                prompt = params.get("prompt", step.action)
                model_id = model_registry.route_task(prompt)
                output, _ = model_registry.execute_prompt(model_id, prompt)
                return {"success": True, "output": output, "tool": "direct_llm_fallback"}

        except Exception as exc:
            logger.error("Step %s failed: %s", step.step_id, exc)
            return {"success": False, "error": str(exc), "tool": tool_name}

    def observe_tool_result(self, step: PlanStep, result: dict) -> None:
        """Phase 3: feed tool output back into context for next steps."""
        self.context[step.step_id] = result.get("output", "")

    def update_task_state(self, task_id: str, new_status: str) -> None:
        """Phase 3: persist task state via TaskStateMachine + DB."""
        from database.models import Task
        if self.db:
            task = self.db.query(Task).filter(Task.id == task_id).first()
            if task:
                task.status = new_status
                self.db.commit()

    def retry_step(self, step: PlanStep, reason: str, task_id: str = "unknown") -> dict:
        """Phase 3: retry a single step with a corrective hint injected into params."""
        step.params["correction_hint"] = reason
        from tools.registry import tool_registry
        return self.execute_step(step, tool_registry, task_id=task_id)

    def _write_step_to_db(self, task_id: str, step: PlanStep, result: dict) -> None:
        """Write a completed/failed step record to task_steps table."""
        if not self.db:
            return
        try:
            from database.models import TaskStep
            ts = TaskStep(
                task_id=task_id,
                action=f"[{step.step_id}] {step.action}",
                result=json.dumps({"success": result.get("success"), "output": str(result.get("output", ""))[:2000]}),
            )
            self.db.add(ts)
            self.db.commit()
        except Exception as exc:
            if self.db:
                self.db.rollback()
            logger.warning("Failed to write TaskStep to DB: %s", exc)
