import os
import sys
import pytest
from fastapi.testclient import TestClient
from api.auth import get_current_user, UserInfo
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from main import app
from database.session import get_db, Base
from database.models import ModelRoute, Task
from models.registry import ModelRegistry, OLLAMA_CODING_MODEL, OLLAMA_REASONING_MODEL
from orchestrator.planner import Planner
from sandbox.manager import SandboxManager
from rag.ingest import generate_embeddings, store_chunks
from ocr.processor import run_ocr, calculate_ocr_confidence

# Setup test DB
SQLALCHEMY_DATABASE_URL = "sqlite:///./test_phase2_qa.db"
engine = create_engine(SQLALCHEMY_DATABASE_URL, connect_args={"check_same_thread": False})
TestingSessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)

Base.metadata.create_all(bind=engine)

def override_get_db():
    try:
        db = TestingSessionLocal()
        yield db
    finally:
        db.close()

@pytest.fixture(autouse=True)
def setup_test_deps():
    app.dependency_overrides.clear()
    app.dependency_overrides[get_db] = override_get_db
    app.dependency_overrides[get_current_user] = lambda: UserInfo(username='operator', role='operator')
    yield
    app.dependency_overrides.clear()

client = TestClient(app)
app.dependency_overrides[get_current_user] = lambda: UserInfo(username='operator', role='operator')

# â”€â”€ 1. API & Database Integration Test â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€
def test_api_task_routing():
    # Test coding route
    res = client.post("/api/tasks", json={"prompt": "Write a python function to add numbers"})
    assert res.status_code == 200, res.text
    data = res.json()
    assert data["model_used"] == OLLAMA_CODING_MODEL
    
    # Test reasoning route
    res = client.post("/api/tasks", json={"prompt": "Explain the history of Rome"})
    assert res.status_code == 200, res.text
    data2 = res.json()
    assert data2["model_used"] == OLLAMA_REASONING_MODEL

    # Verify Database Tracking
    db = TestingSessionLocal()
    routes = db.query(ModelRoute).all()
    assert len(routes) >= 2
    coding_route = [r for r in routes if r.task_id == data["task_id"]][0]
    assert coding_route.task_type == "CODING"
    assert coding_route.selected_model == OLLAMA_CODING_MODEL
    
    reasoning_route = [r for r in routes if r.task_id == data2["task_id"]][0]
    assert reasoning_route.task_type == "REASONING"
    assert reasoning_route.selected_model == OLLAMA_REASONING_MODEL
    db.close()


# â”€â”€ 2. DoD 20-Prompt Test â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€
def test_dod_20_prompt_routing():
    registry = ModelRegistry()
    coding_prompts = [
        "Write a Python script for web scraping",
        "How do I debug a NullPointerException in Java?",
        "Create a bash script to backup my directory",
        "Write a SQL query to join these tables",
        "Explain this C++ code snippet",
        "Write a React component for a login form",
        "How to use lambda functions in Python",
        "Implement quicksort in Python",
        "Fix the syntax error in my Javascript code",
        "Write a regex to match email addresses"
    ]
    reasoning_prompts = [
        "Explain the theory of relativity",
        "What are the main themes in 1984?",
        "Write a poem about the ocean",
        "How do I negotiate a salary?",
        "Summarize the French Revolution",
        "Give me a recipe for chocolate cake",
        "What is the capital of Australia?",
        "Translate 'hello' to French",
        "Give me 5 tips for public speaking",
        "What are the benefits of meditation?"
    ]

    correct_routing = 0
    total = len(coding_prompts) + len(reasoning_prompts)

    for p in coding_prompts:
        if registry.route_task(p) == OLLAMA_CODING_MODEL:
            correct_routing += 1
            
    for p in reasoning_prompts:
        if registry.route_task(p) == OLLAMA_REASONING_MODEL:
            correct_routing += 1

    accuracy = correct_routing / total
    assert accuracy >= 0.95, f"Routing accuracy {accuracy*100}% is below 95% DoD"


# â”€â”€ 3. Sandbox Edge Cases â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€
def test_sandbox_infinite_loop():
    manager = SandboxManager()
    # Code that sleeps to simulate timeout
    code = "import time\nwhile True: time.sleep(1)"
    result = manager.execute_python(code, timeout_seconds=1)
    assert result["exit_code"] == -1
    assert "timed out" in result["stderr"].lower()

def test_sandbox_syntax_error():
    manager = SandboxManager()
    result = manager.execute_python("print('Missing closing parenthesis")
    assert result["exit_code"] != 0
    assert "SyntaxError" in result["stderr"]


# â”€â”€ 4. RAG Qdrant Storage Test â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€
def test_rag_qdrant_memory_storage():
    chunks = [
        {"chunk_index": 0, "text": "This is test chunk 1", "vector": [0.1]*768},
        {"chunk_index": 1, "text": "This is test chunk 2", "vector": [0.2]*768},
    ]
    # Should not throw errors if qdrant-client works in memory
    store_chunks(chunks, collection_name="test_collection")

def test_generate_embeddings_fallback():
    # If ollama is missing, it should fallback to mock zero vectors of length 768
    chunks = [{'text': 'hello', 'chunk_index': 0}]
    res = generate_embeddings(chunks)
    assert 'vector' in res[0]
    assert len(res[0]['vector']) == 768

# â”€â”€ 5. OCR Execution Test â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€
def test_run_ocr_empty_or_invalid():
    # Invalid image bytes should gracefully error without crashing
    res = run_ocr(b"not an image")
    assert res["status"] == "error"
    assert "message" in res