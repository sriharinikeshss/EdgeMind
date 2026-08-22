import sys
import os

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

# ── Router & Registry tests ──────────────────────────────────────────────────
from models.registry import ModelRegistry, OLLAMA_CODING_MODEL, OLLAMA_REASONING_MODEL
from orchestrator.planner import Planner

def test_classify_task():
    planner = Planner()
    assert planner.classify_task("Write a python script") == "CODING"
    assert planner.classify_task("Extract text from this image") == "VISION"
    assert planner.classify_task("According to the sop, what should I do?") == "RAG"
    assert planner.classify_task("What is the meaning of life?") == "REASONING"

def test_score_models():
    reg = ModelRegistry()
    scores = reg.score_models("CODING")
    assert scores[OLLAMA_CODING_MODEL] > scores[OLLAMA_REASONING_MODEL]

    scores = reg.score_models("REASONING")
    assert scores[OLLAMA_REASONING_MODEL] > scores[OLLAMA_CODING_MODEL]

def test_route_task():
    reg = ModelRegistry()
    # It classifies and routes
    model_id = reg.route_task("Can you debug this bash script?")
    assert model_id == OLLAMA_CODING_MODEL

    model_id = reg.route_task("Explain quantum mechanics")
    assert model_id == OLLAMA_REASONING_MODEL


# ── Sandbox bare execution tests ─────────────────────────────────────────────
from sandbox.manager import SandboxManager

def test_execute_python_success():
    manager = SandboxManager()
    result = manager.execute_python("print('Hello from sandbox!')")
    assert result["exit_code"] == 0
    assert "Hello from sandbox!" in result["stdout"]

def test_execute_python_error():
    manager = SandboxManager()
    result = manager.execute_python("1 / 0")
    assert result["exit_code"] != 0
    assert "ZeroDivisionError" in result["stderr"]


# ── OCR Processor tests ──────────────────────────────────────────────────────
from ocr.processor import calculate_ocr_confidence

def test_calculate_ocr_confidence_valid():
    ocr_result = {
        "status": "ok",
        "data": {
            "conf": ["-1", "90", "80", "100", "-1", "90"]
        }
    }
    # Valid confidences: 90, 80, 100, 90. Avg = 360 / 4 = 90. Normalized = 0.9.
    assert calculate_ocr_confidence(ocr_result) == 0.9

def test_calculate_ocr_confidence_invalid():
    assert calculate_ocr_confidence({"status": "error"}) == 0.0
    assert calculate_ocr_confidence({"status": "ok", "data": {"conf": ["-1"]}}) == 0.0
    assert calculate_ocr_confidence({}) == 0.0
