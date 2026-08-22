import pytest
from tools.registry import tool_registry, ToolDefinition
from sandbox.manager import sandbox_manager

def test_tool_registration():
    tools = tool_registry.list_tools()
    assert "execute_python" in tools
    assert "calculator" in tools
    assert "write_file" in tools

def test_tool_permission_check():
    assert tool_registry.check_tool_permission("write_file", "admin") == True
    assert tool_registry.check_tool_permission("write_file", "viewer") == False
    assert tool_registry.check_tool_permission("calculator", "viewer") == True

def test_validate_tool_arguments():
    # valid: explicit code
    assert tool_registry.validate_tool_arguments("execute_python", {"code": "print('hello')"}) == True
    # valid: no code at all — the handler falls back to generating code from
    # a prompt/action description, so this must NOT be rejected pre-execution
    # (a planner step that only describes what to run is a normal case; see
    # the system-test finding that this used to make execute_python
    # unreachable through the real agent loop).
    assert tool_registry.validate_tool_arguments("execute_python", {}) == True
    # invalid: wrong type for a declared property
    assert tool_registry.validate_tool_arguments("execute_python", {"code": ["not", "a", "string"]}) == False

def test_execute_python_in_sandbox():
    # test sandbox manager
    sandbox_id = sandbox_manager.create_sandbox(task_id="test")
    res = sandbox_manager.execute_in_sandbox(sandbox_id, "print('hello from docker sandbox')")
    sandbox_manager.destroy_sandbox(sandbox_id)
    assert res['exit_code'] == 0
    assert 'hello from docker sandbox' in res['stdout']
from orchestrator.executor import Executor
from orchestrator.planner import ExecutionPlan, PlanStep

def test_executor_validation_failure():
    # write_file still has a strict "required" schema (path, content), unlike
    # execute_python — which deliberately no longer requires "code" so the
    # planner's LLM-generated steps can fall back to prompt-driven code
    # generation instead of being rejected pre-execution (see system-test
    # finding: this used to make execute_python unreachable via the real
    # agent loop whenever the plan put code in the step description).
    plan = ExecutionPlan(
        task_id="test",
        steps=[
            PlanStep(
                step_id="step_1",
                action="bad arguments",
                tool="write_file",
                params={"not_path_or_content": "print('hi')"}
            )
        ]
    )
    executor = Executor()
    res = executor.execute_plan(plan)
    assert res['status'] == 'FAILED'
    assert res['events'][-1]['type'] == 'plan_failed'
    failed_event = [e for e in res['events'] if e['type'] == 'step_failed'][0]
    assert "Invalid arguments" in failed_event['error']
def disabled_test_log_tool_call():
    from database.session import SessionLocal
    from database.models import ToolCall
    
    db = SessionLocal()
    tool_registry.log_tool_call(db, task_id="test_task", tool_name="calculator", arguments={"expression": "1+1"}, result=2, status="COMPLETED")
    
    call = db.query(ToolCall).filter(ToolCall.task_id == "test_task").first()
    assert call is not None
    assert call.tool_name == "calculator"
    assert call.status == "COMPLETED"
    db.close()
def disabled_test_log_tool_call_2():
    from database.session import SessionLocal
    from database.models import ToolCall, Task
    import uuid
    
    db = SessionLocal()
    tid = str(uuid.uuid4())
    t = Task(id=tid, description="test")
    db.add(t)
    db.commit()
    
    tool_registry.log_tool_call(db, task_id=tid, tool_name="calculator", arguments={"expression": "1+1"}, result=2, status="COMPLETED")
    
    call = db.query(ToolCall).filter(ToolCall.task_id == tid).first()
    assert call is not None
    assert call.tool_name == "calculator"
    assert call.status == "COMPLETED"
    
    db.delete(call)
    db.delete(t)
    db.commit()
    db.close()
def test_log_tool_call():
    from database.session import SessionLocal
    from database.models import ToolCall, Task
    import uuid
    
    db = SessionLocal()
    tid = str(uuid.uuid4())
    t = Task(id=tid, description="test")
    db.add(t)
    db.commit()
    
    tool_registry.log_tool_call(db, task_id=tid, tool_name="calculator", arguments={"expression": "1+1"}, result=2, status="COMPLETED")
    
    call = db.query(ToolCall).filter(ToolCall.task_id == tid).first()
    assert call is not None
    assert call.tool_name == "calculator"
    assert call.status == "COMPLETED"
    
    db.query(ToolCall).filter(ToolCall.task_id == tid).delete()
    db.query(Task).filter(Task.id == tid).delete()
    db.commit()
    db.close()


# ── Phase 4 gap-closure: Security Engine, audit trail, RBAC fast-fail ──────────
from fastapi.testclient import TestClient
from main import app
from database.session import Base, engine, get_db
from sqlalchemy.orm import sessionmaker
import json as _json

TestingSessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)


def _override_get_db():
    db = TestingSessionLocal()
    try:
        yield db
    finally:
        db.close()


def test_security_engine_authorize_tool():
    from security.engine import authorize_tool, check_role_permission

    assert check_role_permission("admin", ["admin", "operator"]) is True
    assert check_role_permission("viewer", ["admin", "operator"]) is False
    assert authorize_tool("write_file", "viewer", ["admin", "operator"]) is False
    assert authorize_tool("write_file", "admin", ["admin", "operator"]) is True


def test_viewer_user_can_login():
    Base.metadata.create_all(bind=engine)
    app.dependency_overrides[get_db] = _override_get_db
    client = TestClient(app)
    try:
        response = client.post(
            "/api/auth/login",
            data={"username": "viewer", "password": "kavach123"},
        )
        assert response.status_code == 200
        assert response.json()["role"] == "viewer"
    finally:
        app.dependency_overrides.clear()


def test_agent_permission_denied_no_retry(monkeypatch):
    """
    DoD gap-closure: a Viewer role is blocked from a write tool (write_file),
    demonstrated end-to-end through the agent loop (not just the unit-level
    check_tool_permission test above). Also verifies the denial is written
    to BOTH tool_calls and audit_logs, and is never retried.
    """
    from models.registry import registry
    from api.auth import get_current_user, UserInfo
    from database.models import AuditLog, Task, TaskStep, ToolCall

    Base.metadata.create_all(bind=engine)
    app.dependency_overrides[get_db] = _override_get_db
    app.dependency_overrides[get_current_user] = lambda: UserInfo(username="viewer_user", role="viewer")
    client = TestClient(app)

    def mock_execute_prompt(model_id, prompt):
        if "You are a task planner." in prompt:
            plan = {
                "steps": [
                    {"step_id": "s1", "action": "Write result to file", "tool": "write_file",
                     "params": {"path": "/tmp/out.txt", "content": "hello"}},
                ]
            }
            return _json.dumps(plan), 100.0
        return "Mock response", 50.0

    monkeypatch.setattr(registry, "execute_prompt", mock_execute_prompt)

    try:
        response = client.post("/api/agent", json={"prompt": "Write the result to a file"})
        assert response.status_code == 200
        data = response.json()

        assert data["status"] == "FAILED"
        assert data["steps"][0]["success"] is False
        assert "not allowed" in data["steps"][0]["error"]

        # A permission denial must not be retried like a transient tool failure
        event_types = [e["type"] for e in data["events"]]
        assert "step_retrying" not in event_types
        assert "step_failed" in event_types

        db = TestingSessionLocal()
        denied_call = db.query(ToolCall).filter(ToolCall.task_id == data["task_id"]).first()
        assert denied_call is not None
        assert denied_call.status == "DENIED"

        audit_entry = (
            db.query(AuditLog)
            .filter(AuditLog.action == "TOOL_CALL")
            .filter(AuditLog.details.like(f"%{data['task_id']}%"))
            .first()
        )
        assert audit_entry is not None
        assert "status=DENIED" in audit_entry.details

        from database.models import ModelRoute
        db.query(ToolCall).filter(ToolCall.task_id == data["task_id"]).delete()
        db.query(TaskStep).filter(TaskStep.task_id == data["task_id"]).delete()
        db.query(ModelRoute).filter(ModelRoute.task_id == data["task_id"]).delete()
        db.query(Task).filter(Task.id == data["task_id"]).delete()
        db.commit()
        db.close()
    finally:
        app.dependency_overrides.clear()
