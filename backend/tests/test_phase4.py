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
    # valid
    assert tool_registry.validate_tool_arguments("execute_python", {"code": "print('hello')"}) == True
    # invalid
    assert tool_registry.validate_tool_arguments("execute_python", {}) == False

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
    plan = ExecutionPlan(
        task_id="test",
        steps=[
            PlanStep(
                step_id="step_1",
                action="bad arguments",
                tool="execute_python",
                params={"not_code": "print('hi')"}
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
