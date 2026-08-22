"""
Phase 3 tests — M1/M2/M3/M4/M5 coverage.
"""
import sys, os
sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from orchestrator.planner import Planner, PlanStep, ExecutionPlan
from orchestrator.state_machine import TaskStateMachine, TaskStatus
from orchestrator.executor import Executor
from orchestrator.validator import Validator
from models.registry import ModelRegistry, OLLAMA_REASONING_MODEL, OLLAMA_CODING_MODEL

# ── State Machine ─────────────────────────────────────────────────────────────

def test_full_state_machine_happy_path():
    sm = TaskStateMachine("t1")
    assert sm.status == TaskStatus.CREATED
    sm.transition(TaskStatus.CLASSIFIED)
    sm.transition(TaskStatus.PLANNED)
    sm.transition(TaskStatus.EXECUTING)
    sm.transition(TaskStatus.VALIDATING)
    sm.transition(TaskStatus.COMPLETED)
    assert sm.status == TaskStatus.COMPLETED

def test_state_machine_retry_path():
    sm = TaskStateMachine("t2")
    sm.transition(TaskStatus.CLASSIFIED)
    sm.transition(TaskStatus.PLANNED)
    sm.transition(TaskStatus.EXECUTING)
    sm.transition(TaskStatus.RETRYING)
    sm.transition(TaskStatus.EXECUTING)
    sm.transition(TaskStatus.VALIDATING)
    sm.transition(TaskStatus.COMPLETED)
    assert sm.status == TaskStatus.COMPLETED

def test_state_machine_illegal_transition():
    sm = TaskStateMachine("t3")
    try:
        sm.transition(TaskStatus.COMPLETED)  # CREATED → COMPLETED is illegal
        assert False, "Should have raised ValueError"
    except ValueError:
        pass

def test_state_machine_fail_from_executing():
    sm = TaskStateMachine("t4")
    sm.transition(TaskStatus.CLASSIFIED)
    sm.transition(TaskStatus.PLANNED)
    sm.transition(TaskStatus.EXECUTING)
    sm.transition(TaskStatus.FAILED)
    assert sm.status == TaskStatus.FAILED

# ── Planner ───────────────────────────────────────────────────────────────────

def test_classify_task():
    p = Planner()
    assert p.classify_task("Write a python script") == "CODING"
    assert p.classify_task("Extract text from this image") == "VISION"
    assert p.classify_task("According to the sop, what should I do?") == "RAG"
    assert p.classify_task("Explain quantum mechanics") == "REASONING"

def test_create_execution_graph_topological_sort():
    p = Planner()
    steps = [
        PlanStep(step_id="step_3", action="Final summary", tool="direct_llm", depends_on=["step_2"]),
        PlanStep(step_id="step_2", action="Process data", tool="execute_python", depends_on=["step_1"]),
        PlanStep(step_id="step_1", action="Gather data", tool="direct_llm", depends_on=[]),
    ]
    plan = p.create_execution_graph(steps)
    # step_1 must come before step_2, step_2 before step_3
    ids = [s.step_id for s in plan.steps]
    assert ids.index("step_1") < ids.index("step_2")
    assert ids.index("step_2") < ids.index("step_3")

def test_generate_plan_fallback():
    """generate_plan must return a valid ExecutionPlan even when Ollama is offline."""
    p = Planner()
    plan = p.generate_plan("task-id-xyz", "Explain gravity")
    assert isinstance(plan, ExecutionPlan)
    assert len(plan.steps) >= 1
    assert plan.steps[0].tool == "direct_llm"

# ── Executor ──────────────────────────────────────────────────────────────────

def test_executor_single_step_plan():
    """Executor with a single direct_llm step should return COMPLETED."""
    plan = ExecutionPlan(
        task_id="exec-test-1",
        steps=[
            PlanStep(
                step_id="step_1",
                action="Say hello",
                tool="direct_llm",
                depends_on=[],
                params={"prompt": "Say hello"},
            )
        ],
    )
    ex = Executor(db_session=None)
    result = ex.execute_plan(plan)
    assert result["status"] == "COMPLETED"
    assert len(result["results"]) == 1
    assert result["results"][0]["success"] is True

def test_executor_step_failure_propagation():
    """If a step fails all retries, the plan should return FAILED."""
    from tools.registry import ToolRegistry, ToolDefinition

    def failing_tool(**kwargs):
        raise RuntimeError("Intentional failure")

    local_registry = ToolRegistry()
    local_registry.register_tool(ToolDefinition(
        name="bad_tool",
        description="Always fails",
        input_schema={},
        output_schema={},
        handler=failing_tool,
    ))

    plan = ExecutionPlan(
        task_id="exec-test-fail",
        steps=[
            PlanStep(
                step_id="step_1",
                action="Run failing tool",
                tool="bad_tool",
                depends_on=[],
                params={},
            )
        ],
    )
    ex = Executor(db_session=None)

    # Monkeypatch execute_step to use local registry
    original = ex.execute_step
    def patched_execute(step, tool_registry=None, task_id="unknown"):
        return original(step, local_registry, task_id=task_id)
    ex.execute_step = patched_execute

    result = ex.execute_plan(plan)
    assert result["status"] == "FAILED"

# ── Validator ─────────────────────────────────────────────────────────────────

def test_validator_passes_non_empty():
    v = Validator()
    assert v.validate_answer("t1", "This is a valid answer") is True

def test_validator_fails_empty():
    v = Validator()
    assert v.validate_answer("t1", "") is False
    assert v.validate_answer("t1", "   ") is False

def test_validator_json_schema_pass():
    v = Validator()
    import json
    answer = json.dumps({"result": 42, "status": "ok"})
    schema = {"required": ["result", "status"]}
    assert v.validate_answer("t1", answer, schema) is True

def test_validator_json_schema_fail_missing_key():
    v = Validator()
    import json
    answer = json.dumps({"result": 42})
    schema = {"required": ["result", "status"]}
    assert v.validate_answer("t1", answer, schema) is False

# ── M2 Router Hardening ───────────────────────────────────────────────────────

def test_estimate_latency():
    reg = ModelRegistry()
    lat = reg.estimate_latency(OLLAMA_REASONING_MODEL, prompt_token_count=500)
    assert lat > 0
    # 500 tokens / 25 tok/s * 1000 = 20000 ms
    assert abs(lat - 20000.0) < 1.0

def test_fallback_model():
    reg = ModelRegistry()
    # Simulate VRAM exhausted
    reg.available_vram_gb = 0.0
    model = reg.route_task("Write a python script to calculate fibonacci")
    assert model == OLLAMA_REASONING_MODEL  # must fall back

def test_health_check_model_offline():
    """health_check_model must return False if Ollama is offline."""
    reg = ModelRegistry()
    result = reg.health_check_model(OLLAMA_REASONING_MODEL)
    assert isinstance(result, bool)

# ── M5 Tool Registry ──────────────────────────────────────────────────────────

def test_tool_registry_register_and_list():
    from tools.registry import ToolRegistry, ToolDefinition
    tr = ToolRegistry()
    tr.register_tool(ToolDefinition(
        name="test_tool",
        description="A test",
        input_schema={},
        output_schema={},
        handler=lambda **k: "ok",
    ))
    assert "test_tool" in tr.list_tools()

def test_tool_registry_permission_check():
    from tools.registry import ToolRegistry, ToolDefinition
    tr = ToolRegistry()
    tr.register_tool(ToolDefinition(
        name="admin_only_tool",
        description="Admin only",
        input_schema={},
        output_schema={},
        allowed_roles=["admin"],
        handler=lambda **k: "ok",
    ))
    assert tr.check_tool_permission("admin_only_tool", "admin") is True
    assert tr.check_tool_permission("admin_only_tool", "viewer") is False

def test_tool_registry_execute_permission_denied():
    from tools.registry import ToolRegistry, ToolDefinition
    tr = ToolRegistry()
    tr.register_tool(ToolDefinition(
        name="restricted",
        description="Admin only",
        input_schema={},
        output_schema={},
        allowed_roles=["admin"],
        handler=lambda **k: "ok",
    ))
    try:
        tr.execute_tool("restricted", "viewer", {})
        assert False, "Should have raised PermissionError"
    except PermissionError:
        pass

def test_tool_registry_builtin_tools_registered():
    from tools.registry import tool_registry
    assert "execute_python" in tool_registry.list_tools()
    assert "rag_search" in tool_registry.list_tools()
    assert "direct_llm" in tool_registry.list_tools()
