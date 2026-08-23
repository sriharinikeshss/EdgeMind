"""
Phase 5 tests — OCR/vision merged into the agent pipeline.

Tesseract is not installed on the local dev machine (confirmed via
pytesseract.get_tesseract_version() raising TesseractNotFoundError), so
these tests monkeypatch ocr.processor.run_ocr with canned results rather
than depending on a real OCR engine, matching the existing convention in
test_qa_phase2.py / test_qa_phase3.py.
"""
import base64
import json as _json

import pytest
from fastapi.testclient import TestClient

from main import app
from database.session import Base, engine, get_db
from sqlalchemy.orm import sessionmaker

TestingSessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)


def _override_get_db():
    db = TestingSessionLocal()
    try:
        yield db
    finally:
        db.close()


# A tiny valid 1x1 PNG, base64-encoded (matches the fixture used in test_qa_phase3.py)
_PIXEL_PNG_B64 = base64.b64encode(
    b'\x89PNG\r\n\x1a\n\x00\x00\x00\rIHDR\x00\x00\x00\x01\x00\x00\x00\x01\x08\x06\x00\x00\x00'
    b'\x1f\x15\xc4\x89\x00\x00\x00\nIDATx\x9cc\x00\x01\x00\x00\x05\x00\x01\r\n-\xb4\x00\x00\x00\x00IEND\xaeB`\x82'
).decode("utf-8")


def _canned_ocr_data():
    """Word-level pytesseract-style data mixing high/low confidence words plus an empty row."""
    return {
        "text": ["Pressure", "", "valve", "prssur3", "OK"],
        "conf": ["92", "-1", "88", "35", "40"],
        "left": [10, 0, 50, 90, 130],
        "top": [10, 0, 10, 10, 10],
        "width": [40, 0, 30, 35, 20],
        "height": [12, 0, 12, 12, 12],
    }


def _canned_ocr_result():
    return {"status": "ok", "text": "Pressure valve prssur3 OK", "data": _canned_ocr_data(), "words": [{"text": "Pressure", "confidence": 0.92, "bbox": {"x": 10, "y": 10, "w": 40, "h": 12}}, {"text": "valve", "confidence": 0.88, "bbox": {"x": 50, "y": 10, "w": 30, "h": 12}}, {"text": "prssur3", "confidence": 0.35, "bbox": {"x": 90, "y": 10, "w": 35, "h": 12}}, {"text": "OK", "confidence": 0.4, "bbox": {"x": 130, "y": 10, "w": 20, "h": 12}}], "full_text": "Pressure valve prssur3 OK"}


# ── flag_low_confidence_regions() unit tests ────────────────────────────────

def test_flag_low_confidence_regions_filters_correctly():
    from vision.multimodal_processor import flag_low_confidence_regions

    flagged = flag_low_confidence_regions(_canned_ocr_result(), threshold=0.6)
    flagged_texts = {f["text"] for f in flagged}

    # "prssur3" (35%) and "OK" (40%) are below threshold; "Pressure" (92%) and
    # "valve" (88%) are not; the empty-text row must never be flagged.
    assert flagged_texts == {"prssur3", "OK"}
    assert "" not in flagged_texts
    for f in flagged:
        assert 0.0 <= f["confidence"] < 0.6
        assert len(f["bbox"]) == 4


def test_flag_low_confidence_regions_non_ok_status_returns_empty():
    from vision.multimodal_processor import flag_low_confidence_regions

    assert flag_low_confidence_regions({"status": "error"}) == []


# ── analyze_scanned_document tool handler ───────────────────────────────────

def test_analyze_scanned_document_handler(monkeypatch):
    import ocr.processor as ocr_processor
    from tools.registry import _analyze_scanned_document_handler

    import vision.multimodal_processor
    monkeypatch.setattr(vision.multimodal_processor, "run_ocr", lambda image_bytes: _canned_ocr_result())

    result = _analyze_scanned_document_handler(image_base64=_PIXEL_PNG_B64, filename="report.png", task_id="t1")

    assert result["status"] == "ok"
    assert "Pressure valve prssur3 OK" in result["stdout"]
    assert len(result.get("flagged_regions", [])) == 2
    assert len(result["flagged_regions"]) == 2


def test_analyze_scanned_document_handler_no_image():
    from tools.registry import _analyze_scanned_document_handler

    result = _analyze_scanned_document_handler(task_id="t1")
    assert result["status"] == "error"
    assert "No image provided" in result["stdout"]


def test_analyze_engineering_drawing_stub_is_graceful():
    from tools.registry import _analyze_engineering_drawing_handler

    result = _analyze_engineering_drawing_handler(image_base64=_PIXEL_PNG_B64, task_id="t1")
    assert result["status"] in ["unavailable", "error"]
    assert "implemented" in result.get("stdout", "") or "error" in result.get("status", "")


# ── End-to-end /api/agent with an attached image ────────────────────────────

def test_agent_with_image_runs_ocr_step_first(monkeypatch):
    """
    Phase 5 integration point: an image attached to the agent request must
    deterministically produce step_ocr as the first executed step, whose
    extracted text (and low-confidence flags) flow into the final output.
    """
    import ocr.processor as ocr_processor
    from models.registry import registry

    from api.auth import get_current_user, UserInfo

    Base.metadata.create_all(bind=engine)
    app.dependency_overrides[get_db] = _override_get_db
    app.dependency_overrides[get_current_user] = lambda: UserInfo(username="tester", role="operator")
    client = TestClient(app)

    import vision.multimodal_processor
    monkeypatch.setattr(vision.multimodal_processor, "run_ocr", lambda image_bytes: _canned_ocr_result())

    def mock_execute_prompt(model_id, prompt):
        if "You are a task planner." in prompt:
            plan = {
                "steps": [
                    {"step_id": "s1", "action": "Summarize the extracted findings", "tool": "direct_llm",
                     "depends_on": ["step_ocr"], "params": {}},
                ]
            }
            return _json.dumps(plan), 100.0
        return "Summary of findings", 50.0

    monkeypatch.setattr(registry, "execute_prompt", mock_execute_prompt)

    try:
        response = client.post("/api/agent", json={
            "prompt": "Read this inspection report and summarize it",
            "image_base64": _PIXEL_PNG_B64,
            "filename": "report.png",
        })
        assert response.status_code == 200
        data = response.json()

        assert data["status"] in ["COMPLETED", "FAILED"]
        assert data["steps"][0]["step_id"] == "step_ocr"
        assert data["steps"][0]["tool"] == "analyze_scanned_document"
        assert "2 low-confidence region(s)" in data["final_output"]
    finally:
        app.dependency_overrides.clear()


def test_agent_without_image_has_no_ocr_step(monkeypatch):
    """Regression: no image attached must behave exactly as before Phase 5."""
    from models.registry import registry
    from api.auth import get_current_user, UserInfo

    Base.metadata.create_all(bind=engine)
    app.dependency_overrides[get_db] = _override_get_db
    app.dependency_overrides[get_current_user] = lambda: UserInfo(username="tester", role="operator")
    client = TestClient(app)

    def mock_execute_prompt(model_id, prompt):
        if "You are a task planner." in prompt:
            plan = {"steps": [{"step_id": "s1", "action": "Answer", "tool": "direct_llm", "depends_on": [], "params": {}}]}
            return _json.dumps(plan), 100.0
        return "An answer", 50.0

    monkeypatch.setattr(registry, "execute_prompt", mock_execute_prompt)

    try:
        response = client.post("/api/agent", json={"prompt": "What is 2+2?"})
        assert response.status_code == 200
        data = response.json()
        assert all(s["tool"] != "analyze_scanned_document" for s in data["steps"])
    finally:
        app.dependency_overrides.clear()
