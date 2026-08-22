"""
Phase 5: Vision & Multimodal Pipeline Tests.
"""
import io
import base64
import pytest
from PIL import Image, ImageDraw

from ocr.processor import run_ocr, crop_image_region, calculate_ocr_confidence
from vision.multimodal_processor import (
    classify_image_type,
    flag_low_confidence_regions,
    analyze_scanned_document,
    analyze_engineering_drawing,
    generate_visual_evidence,
    process_multimodal_task
)
from tools.registry import tool_registry
from fastapi.testclient import TestClient
from main import app

client = TestClient(app)


def _create_sample_image(text: str = "INSPECTION REPORT\nDate: 2026-08-23\nStatus: PASSED\nPressure: 105 PSI", size=(400, 200)) -> bytes:
    img = Image.new("RGB", size, color="white")
    draw = ImageDraw.Draw(img)
    draw.text((10, 10), text, fill="black")
    buf = io.BytesIO()
    img.save(buf, format="PNG")
    return buf.getvalue()


def _create_pid_drawing_image() -> bytes:
    text = "P&ID SCHEMATIC\nDWG NO: PID-9001\nV-101 Gate Valve\nPT-202 Pressure Transmitter\nTI-303 Temp Indicator"
    return _create_sample_image(text, size=(600, 300))


def test_ocr_bounding_box_extraction():
    """Verify run_ocr returns structured word bounding boxes and confidence scores."""
    img_bytes = _create_sample_image()
    res = run_ocr(img_bytes)

    assert res["status"] == "ok"
    assert "words" in res
    assert "image_size" in res
    assert isinstance(res["words"], list)
    assert res["average_confidence"] >= 0.0


def test_crop_image_region():
    """Verify crop_image_region extracts sub-regions accurately."""
    img_bytes = _create_sample_image()
    bbox = {"x": 10, "y": 10, "w": 50, "h": 30}
    cropped_bytes = crop_image_region(img_bytes, bbox)

    assert isinstance(cropped_bytes, bytes)
    cropped_img = Image.open(io.BytesIO(cropped_bytes))
    assert cropped_img.size == (50, 30)


def test_flag_low_confidence_regions():
    """Anti-hallucination guardrail: low confidence words (< 70%) must be flagged."""
    mock_ocr_data = {
        "words": [
            {"text": "HighConfidenceWord", "confidence": 0.95, "bbox": {"x": 0, "y": 0, "w": 10, "h": 10}},
            {"text": "LowConfidenceToken", "confidence": 0.55, "bbox": {"x": 20, "y": 20, "w": 15, "h": 15}},
            {"text": "BorderlineToken", "confidence": 0.68, "bbox": {"x": 40, "y": 40, "w": 10, "h": 10}},
        ]
    }
    flags = flag_low_confidence_regions(mock_ocr_data, threshold=0.70)
    assert len(flags) == 2
    flagged_texts = [f["text"] for f in flags]
    assert "LowConfidenceToken" in flagged_texts
    assert "BorderlineToken" in flagged_texts
    assert "HighConfidenceWord" not in flagged_texts


def test_analyze_scanned_document():
    """Verify structured key-values and sections extraction for scanned documents."""
    img_bytes = _create_sample_image("INVOICE REPORT\nInvoice_No: INV-4491\nTotal_Amount: $500\nInspector: Alice")
    doc_res = analyze_scanned_document(img_bytes)

    assert doc_res["status"] == "ok"
    assert doc_res["document_type"] == "scanned_document"
    assert "key_values" in doc_res
    assert "low_confidence_regions" in doc_res
    assert "words_with_boxes" in doc_res


def test_analyze_engineering_drawing():
    """Verify P&ID component tags and instrument detection."""
    img_bytes = _create_pid_drawing_image()
    drawing_res = analyze_engineering_drawing(img_bytes)

    assert drawing_res["status"] == "ok"
    assert drawing_res["document_type"] == "engineering_drawing"
    assert "components" in drawing_res or "instruments" in drawing_res
    assert "low_confidence_regions" in drawing_res


def test_generate_visual_evidence():
    """Verify generation of base64 visual evidence thumbnail."""
    img_bytes = _create_sample_image()
    bbox = {"x": 10, "y": 10, "w": 60, "h": 25}
    ev = generate_visual_evidence(img_bytes, bbox, label="Sample Claim")

    assert ev["status"] == "ok"
    assert ev["thumbnail_b64"].startswith("data:image/png;base64,")
    assert ev["label"] == "Sample Claim"


def test_tool_registry_phase5_tools():
    """Verify all Phase 5 multimodal tools are registered with proper schemas."""
    tools = tool_registry.list_tools()
    assert "run_ocr" in tools
    assert "analyze_scanned_document" in tools
    assert "analyze_engineering_drawing" in tools
    assert "generate_visual_evidence" in tools

    img_bytes = _create_sample_image()
    # Test tool execution through registry
    ocr_exec = tool_registry.execute_tool("run_ocr", user_role="operator", arguments={"image_bytes": img_bytes})
    assert ocr_exec["status"] == "ok"


def test_vision_api_endpoints():
    """Verify FastAPI vision multimodal endpoints."""
    img_bytes = _create_sample_image()
    b64_str = base64.b64encode(img_bytes).decode("utf-8")

    # POST /api/vision/multimodal
    resp = client.post("/api/vision/multimodal", json={"image_base64": b64_str, "task_type": "auto"})
    assert resp.status_code == 200
    data = resp.json()
    assert data["status"] == "ok"
    assert "grounding_prompt" in data

    # POST /api/vision/evidence
    ev_resp = client.post("/api/vision/evidence", json={
        "image_base64": b64_str,
        "bbox": {"x": 0, "y": 0, "w": 50, "h": 50},
        "label": "Test Box"
    })
    assert ev_resp.status_code == 200
    ev_data = ev_resp.json()
    assert ev_data["status"] == "ok"
    assert "thumbnail_b64" in ev_data
