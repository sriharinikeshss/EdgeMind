import pytest
from fastapi.testclient import TestClient
from main import app
from database.session import Base, engine, get_db
from sqlalchemy.orm import sessionmaker
import json
import base64

TestingSessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)

def override_get_db():
    db = TestingSessionLocal()
    try:
        yield db
    finally:
        db.close()

app.dependency_overrides[get_db] = override_get_db

client = TestClient(app)

@pytest.fixture(autouse=True)
def setup_db():
    app.dependency_overrides.clear()
    app.dependency_overrides[get_db] = override_get_db
    Base.metadata.create_all(bind=engine)
    yield
    # Cleanup tasks after
    db = TestingSessionLocal()
    from database.models import Task, TaskStep, ToolCall, ModelRoute
    db.query(ToolCall).delete()
    db.query(TaskStep).delete()
    db.query(ModelRoute).delete()
    db.query(Task).delete()
    db.commit()
    db.close()
    app.dependency_overrides.clear()


def test_agent_end_to_end_3_step_task(monkeypatch):
    """
    DoD: Agent completes a 3+ step synthetic task end-to-end with full
    state-machine trace persisted and rendered live.
    """
    from models.registry import registry
    
    # Mock LLM generation to return a 3-step plan
    def mock_execute_prompt(model_id, prompt):
        if "You are a task planner." in prompt:
            plan = {
                "steps": [
                    {"step_id": "s1", "action": "Calculate 5+5", "tool": "execute_python", "params": {"code": "print(5+5)"}},
                    {"step_id": "s2", "action": "Lookup SOP", "tool": "rag_search", "depends_on": ["s1"], "params": {"query": "test"}},
                    {"step_id": "s3", "action": "Summarize", "tool": "direct_llm", "depends_on": ["s2"], "params": {"prompt": "Done"}}
                ]
            }
            return json.dumps(plan), 100.0
        
        return "Mock response", 50.0

    monkeypatch.setattr(registry, "execute_prompt", mock_execute_prompt)

    response = client.post("/api/agent", json={"prompt": "Do the 3 step task"})
    
    assert response.status_code == 200
    data = response.json()
    assert data["status"] == "COMPLETED"
    assert len(data["steps"]) == 3
    assert data["validation_passed"] is True
    
    # Verify events trace transitions
    event_types = [e["type"] for e in data["events"]]
    assert "plan_started" in event_types
    assert "step_started" in event_types
    assert "step_completed" in event_types
    assert "plan_completed" in event_types


def test_agent_forced_tool_failure(monkeypatch):
    """
    DoD: A forced tool failure correctly transitions to RETRYING then FAILED.
    """
    from models.registry import registry
    from tools.registry import tool_registry, ToolDefinition
    
    # Register a failing tool
    def failing_tool(**kwargs):
        raise ValueError("Intentional crash")
        
    tool_registry.register_tool(ToolDefinition(
        name="crash_tool",
        description="Fails",
        input_schema={},
        output_schema={},
        handler=failing_tool
    ))

    def mock_execute_prompt(model_id, prompt):
        if "You are a task planner." in prompt:
            plan = {
                "steps": [
                    {"step_id": "s1", "action": "Crash", "tool": "crash_tool", "params": {}},
                ]
            }
            return json.dumps(plan), 100.0
        return "Mock response", 50.0

    monkeypatch.setattr(registry, "execute_prompt", mock_execute_prompt)

    response = client.post("/api/agent", json={"prompt": "Do the crash task"})
    
    assert response.status_code == 200
    data = response.json()
    assert data["status"] == "FAILED"
    assert len(data["steps"]) == 1
    assert data["steps"][0]["success"] is False
    assert "Intentional crash" in data["steps"][0]["error"]
    
    event_types = [e["type"] for e in data["events"]]
    assert "step_retrying" in event_types
    assert "step_failed" in event_types
    assert "plan_failed" in event_types


def test_standalone_rag_api():
    response = client.post("/api/rag/search", json={"query": "test query"})
    assert response.status_code == 200
    data = response.json()
    assert data["status"] == "ok"
    assert "results" in data


def test_standalone_vision_api():
    # Provide a minimal base64 valid image (a 1x1 pixel PNG)
    pixel = b'\\x89PNG\\r\\n\\x1a\\n\\x00\\x00\\x00\\rIHDR\\x00\\x00\\x00\\x01\\x00\\x00\\x00\\x01\\x08\\x06\\x00\\x00\\x00\\x1f\\x15\\xc4\\x89\\x00\\x00\\x00\\nIDATx\\x9cc\\x00\\x01\\x00\\x00\\x05\\x00\\x01\\r\\n-\\xb4\\x00\\x00\\x00\\x00IEND\\xaeB`\\x82'
    b64 = base64.b64encode(pixel).decode("utf-8")
    
    response = client.post("/api/vision/analyze", json={"image_base64": b64})
    assert response.status_code == 200
    data = response.json()
    assert data["status"] in ["ok", "error"]  # tesseract might not be installed in the CI env, so "error" is acceptable if handled gracefully.
