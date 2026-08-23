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

    # Phase 9: tools whose output is third-party document content (RAG chunks,
    # OCR/vision extractions) — not the agent's own reasoning — and must be
    # content-type-tagged as untrusted before being folded into a later prompt.
    _UNTRUSTED_CONTEXT_TOOLS = {"rag_search", "analyze_scanned_document", "analyze_engineering_drawing", "run_ocr"}

    def __init__(self, db_session=None, user_role: str = "operator", username: str | None = None):
        self.db = db_session
        self.user_role = user_role
        self.username = username
        self.events: list[dict] = []   # collected step events for WS streaming
        self.context: dict[str, Any] = {}  # accumulates tool outputs across steps
        self.context_sources: dict[str, str] = {}  # step_id -> tool name, for untrusted-content tagging

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
                self.context_sources[step.step_id] = step.tool or "direct_llm"
                self._emit("step_completed", {"step_id": step.step_id, "output": str(step_result.get("output", ""))[:500]})
                self._write_step_to_db(plan.task_id, step, step_result)
                self._write_artifact_if_generated(plan.task_id, step, step_result)
            else:
                step.status = "FAILED"
                self._emit("step_failed", {
                    "step_id": step.step_id,
                    "error": step_result.get("error", "unknown"),
                    "permission_denied": step_result.get("permission_denied", False),
                })
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
            if result.get("permission_denied"):
                # RBAC denials are not transient — retrying won't grant permission.
                logger.warning("Step %s denied by RBAC — not retrying: %s", step.step_id, result.get("error"))
                return result
            if result.get("awaiting_approval"):
                # A human-approval gate isn't resolved by retrying either.
                logger.warning("Step %s awaiting human approval — not retrying: %s", step.step_id, result.get("error"))
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

        # Inject context from previous steps into params. Phase 9: content that
        # came from a document/RAG/vision tool is third-party text, not the
        # agent's own reasoning — tag it as untrusted so it can't be mistaken
        # for an instruction by the next prompt it's folded into.
        params = {**step.params, "task_id": task_id}
        ctx_lines = []
        for sid, out in self.context.items():
            src_tool = self.context_sources.get(sid)
            if src_tool in self._UNTRUSTED_CONTEXT_TOOLS:
                from security.prompt_injection import sanitize_input
                out = sanitize_input(out, source=f"{src_tool}:{sid}")
            ctx_lines.append(f"[{sid}]: {out}")
        ctx_str = "\n".join(ctx_lines)
        if ctx_str:
            if "prompt" in params:
                params["prompt"] = f"{params['prompt']}\n\nContext from previous steps:\n{ctx_str}"
            elif step.action:
                params["prompt"] = f"{step.action}\n\nContext from previous steps:\n{ctx_str}"
        elif "prompt" not in params and step.action:
            params["prompt"] = step.action

        try:
            if tool_name == "direct_llm":
                prompt = params.get("prompt", step.action)
                model_id = model_registry.route_task(prompt)
                output, _ = model_registry.execute_prompt(model_id, prompt)
                return {"success": True, "output": output, "tool": tool_name}

            # Use registered tool
            if registry and tool_name in registry.list_tools():
                # Phase 9 (M1/M6): sensitive tools (write_file, query_db) require
                # an explicit human approval before they run. RBAC authorization
                # (is this role even allowed to call the tool) is a separate,
                # prior question — checked here read-only so an unauthorized
                # role still gets the existing RBAC-denial path (and its
                # ToolCall/audit logging) below, unaffected by this gate.
                if self.db is not None and registry.check_tool_permission(tool_name, self.user_role):
                    from security.approvals import requires_approval, get_active_approval, create_approval_request
                    if requires_approval(tool_name):
                        approval = get_active_approval(self.db, task_id, step.step_id)
                        if approval is None:
                            approval = create_approval_request(
                                self.db, task_id, step.step_id, tool_name, params, requested_by=self.username
                            )
                        if approval.status != "APPROVED":
                            return {
                                "success": False,
                                "error": (
                                    f"Tool '{tool_name}' requires human approval "
                                    f"(status={approval.status}, approval_id={approval.id})."
                                ),
                                "tool": tool_name,
                                "awaiting_approval": True,
                            }

                if not registry.validate_tool_arguments(tool_name, params):
                    return {"success": False, "error": f"Invalid arguments for {tool_name}", "tool": tool_name}
                output = registry.execute_tool(
                    tool_name, user_role=self.user_role, arguments=params, db=self.db, username=self.username
                )

                from tools.registry import ARTIFACT_TOOL_NAMES
                if tool_name in ARTIFACT_TOOL_NAMES and isinstance(output, dict) and output.get("status") == "ok":
                    # Phase 8 DoD: no artifact reaches COMPLETED without passing its
                    # format-specific validator. A failed check fails the step, which
                    # feeds into the existing MAX_RETRIES retry loop below.
                    from orchestrator.validator import Validator
                    check = Validator().validate_artifact(output)
                    if not check.get("valid"):
                        logger.warning("Artifact from %s failed validation: %s", tool_name, check.get("errors"))
                        return {
                            "success": False,
                            "error": f"Artifact failed validation: {'; '.join(check.get('errors', []))}",
                            "tool": tool_name,
                        }
                    output["validation"] = check

                    # Phase 9 (M6): encrypt the artifact at rest, now that Phase 8
                    # has validated the plaintext. No-op unless
                    # ARTIFACT_ENCRYPTION_ENABLED is set (see artifacts/storage.py).
                    from artifacts.storage import encrypt_file_at_rest
                    if output.get("path"):
                        output["encrypted_at_rest"] = encrypt_file_at_rest(output["path"])

                tool_data = None
                if isinstance(output, dict):
                    tool_data = output  # Preserve full raw JSON for frontend Visual Evidence
                    if output.get("grounding_prompt"):
                        clean_output = output["grounding_prompt"]
                    elif output.get("stdout") is not None:
                        clean_output = output["stdout"]
                    else:
                        # Fallback for dicts without standard keys (if any)
                        clean_output = json.dumps(output)
                else:
                    clean_output = str(output)
                return {"success": True, "output": clean_output, "tool": tool_name, "tool_data": tool_data}
            else:
                # Tool not registered yet — use direct_llm as fallback
                prompt = params.get("prompt", step.action)
                model_id = model_registry.route_task(prompt)
                output, _ = model_registry.execute_prompt(model_id, prompt)
                return {"success": True, "output": output, "tool": "direct_llm_fallback"}

        except PermissionError as exc:
            logger.warning("Step %s denied by RBAC: %s", step.step_id, exc)
            return {"success": False, "error": str(exc), "tool": tool_name, "permission_denied": True}
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

    def _write_artifact_if_generated(self, task_id: str, step: PlanStep, result: dict) -> None:
        """Phase 7: persist a generated artifact's metadata to the `artifacts`
        table and emit an `artifact_created` trace event, when this step ran
        one of the artifact-generation tools (generate_docx/xlsx/pdf/csv/json)."""
        from tools.registry import ARTIFACT_TOOL_NAMES

        if step.tool not in ARTIFACT_TOOL_NAMES:
            return
        meta = result.get("tool_data")
        if not isinstance(meta, dict) or meta.get("status") != "ok" or not meta.get("file_hash"):
            return

        self._emit("artifact_created", {
            "task_id": task_id,
            "artifact_id": meta.get("id"),
            "filename": meta.get("filename"),
            "content_type": meta.get("content_type"),
            "file_hash": meta.get("file_hash"),
        })

        if not self.db:
            return
        try:
            from database.models import Artifact
            artifact = Artifact(
                id=meta.get("id"),
                task_id=task_id,
                filename=meta.get("filename"),
                content_type=meta.get("content_type"),
                file_hash=meta.get("file_hash"),
            )
            self.db.add(artifact)
            self.db.commit()
        except Exception as exc:
            self.db.rollback()
            logger.warning("Failed to write Artifact to DB: %s", exc)

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
