"""
Multimodal Vision Processor — Phase 5 implementation (M4).

Core pipeline:
1. classify_image_type(): Classifies images into scanned_document, engineering_drawing, or general.
2. analyze_scanned_document(): Extracts structured text, key-values, and bounding boxes.
3. analyze_engineering_drawing(): Identifies P&ID symbols, tags, instruments, and connections.
4. flag_low_confidence_regions(): Detects low-confidence tokens (< 0.70) to prevent hallucination.
5. generate_visual_evidence(): Generates cropped visual proof snippets for grounding.
"""
from __future__ import annotations
import io
import re
import base64
import logging
from typing import Any
from pathlib import Path

logger = logging.getLogger(__name__)

try:
    from PIL import Image, ImageStat
    _PIL_AVAILABLE = True
except ImportError:
    Image = None
    _PIL_AVAILABLE = False

from ocr.preprocess import preprocess_image, _pil_preprocess
from ocr.processor import run_ocr, crop_image_region, calculate_ocr_confidence


# Regex patterns for engineering drawing tags & key-value detection
_PID_TAG_PATTERN = re.compile(r"\b([A-Z]{1,4}[-_]?[0-9]{2,4}[A-Z]?)\b", re.IGNORECASE)
_KV_PAIR_PATTERN = re.compile(r"^\s*([A-Za-z0-9 _\-\/]+?)\s*[:=]\s*(.+)$")
_VALVE_SYMBOLS = {"valve", "gate valve", "check valve", "ball valve", "globe valve", "control valve"}
_INSTRUMENT_PREFIXES = {"PT", "TT", "FT", "LT", "PI", "TI", "FI", "LI", "PSV", "CV"}


def _ensure_bytes(image_input: bytes | str) -> bytes:
    """Helper to convert filepath or raw bytes into bytes."""
    if isinstance(image_input, (str, Path)):
        with open(image_input, "rb") as f:
            return f.read()
    return image_input


def classify_image_type(image_bytes: bytes) -> str:
    """
    Classifies image input into:
    - 'scanned_document': Text-heavy reports, forms, standard documents.
    - 'engineering_drawing': P&ID diagrams, schematics, blueprints, CAD drawings.
    - 'general': Photographs or other visual media.
    """
    if not _PIL_AVAILABLE or Image is None:
        return "scanned_document"

    try:
        img = Image.open(io.BytesIO(image_bytes))
        w, h = img.size
        aspect_ratio = max(w, h) / min(w, h)

        # Preprocess & run fast OCR sample
        preprocessed = _pil_preprocess(img)
        buf = io.BytesIO()
        preprocessed.save(buf, format="PNG")
        ocr_res = run_ocr(buf.getvalue())

        text = ocr_res.get("text", "") if ocr_res.get("status") == "ok" else ""
        words = ocr_res.get("words", [])

        # Check for P&ID / Drawing indicators
        pid_tags = _PID_TAG_PATTERN.findall(text)
        drawing_keywords = {"p&id", "schematic", "drawing no", "rev", "dwg", "piping", "instrumentation", "scale", "sheet"}
        has_dwg_keywords = any(kw in text.lower() for kw in drawing_keywords)

        # Broad/landscape aspect ratio with diagram tags strongly indicates engineering drawing
        if (has_dwg_keywords or len(pid_tags) >= 3) and (aspect_ratio >= 1.2 or len(words) < 150):
            return "engineering_drawing"

        if len(words) >= 10:
            return "scanned_document"

        return "general"
    except Exception as e:
        logger.warning("Error classifying image type: %s, defaulting to scanned_document", e)
        return "scanned_document"


def flag_low_confidence_regions(ocr_data: dict, threshold: float = 0.70) -> list[dict]:
    """
    Anti-Hallucination Guardrail:
    Finds all extracted words or regions with confidence below threshold (default 70%),
    flagging them with bounding boxes and alert warnings.
    """
    flagged = []
    words = ocr_data.get("words", [])
    for w in words:
        conf = w.get("confidence", 1.0)
        if conf < threshold:
            flagged.append({
                "text": w.get("text", ""),
                "confidence": conf,
                "bbox": w.get("bbox", {}),
                "line_num": w.get("line_num", 0),
                "reason": f"Low OCR confidence ({int(conf * 100)}% < {int(threshold * 100)}%). Verification recommended."
            })
    return flagged


def analyze_scanned_document(image_input: bytes | str) -> dict:
    """
    Analyzes a scanned document or report.
    Returns:
    - full_text: Raw and normalized text.
    - key_values: Extracted form fields (e.g. Date, Order No, Inspector, Values).
    - sections: Detected headers and paragraphs.
    - words_with_boxes: Grounded word bounding boxes.
    - low_confidence_flags: List of tokens flagged under the 70% confidence threshold.
    - average_confidence: Overall OCR reliability score.
    """
    raw_bytes = _ensure_bytes(image_input)
    
    # Step 1: Preprocessing
    if _PIL_AVAILABLE and Image is not None:
        try:
            img = Image.open(io.BytesIO(raw_bytes))
        except Exception as e:
            return {'status': 'error', 'message': f'Cannot parse image: {e}'}
        preprocessed = _pil_preprocess(img)
        buf = io.BytesIO()
        preprocessed.save(buf, format="PNG")
        proc_bytes = buf.getvalue()
    else:
        proc_bytes = raw_bytes

    # Step 2: OCR Extraction
    ocr_result = run_ocr(proc_bytes)
    if ocr_result.get("status") != "ok":
        return {
            "status": "error",
            "message": ocr_result.get("message", "OCR processing failed"),
            "document_type": "scanned_document",
            "structured_data": {}
        }

    text = ocr_result.get("text", "")
    lines = [l.strip() for l in text.split("\n") if l.strip()]
    
    # Step 3: Key-Value and Section Extraction
    key_values = {}
    sections = []
    current_section = {"title": "Header", "content": []}

    for line in lines:
        kv_match = _KV_PAIR_PATTERN.match(line)
        if kv_match:
            k, v = kv_match.groups()
            key_values[k.strip()] = v.strip()
        elif line.isupper() and len(line) > 3 and len(line) < 40:
            if current_section["content"]:
                sections.append(current_section)
            current_section = {"title": line, "content": []}
        else:
            current_section["content"].append(line)

    if current_section["content"] or current_section["title"] != "Header":
        sections.append(current_section)

    # Step 4: Low-confidence detection
    low_conf_flags = flag_low_confidence_regions(ocr_result, threshold=0.70)

    return {
        "status": "ok",
        "document_type": "scanned_document",
        "full_text": text,
        "key_values": key_values,
        "sections": sections,
        "total_words": len(ocr_result.get("words", [])),
        "average_confidence": ocr_result.get("average_confidence", 0.0),
        "low_confidence_regions": low_conf_flags,
        "words_with_boxes": ocr_result.get("words", []),
        "image_size": ocr_result.get("image_size", {})
    }


def analyze_engineering_drawing(image_input: bytes | str) -> dict:
    """
    Analyzes an engineering schematic, P&ID diagram, or CAD drawing.
    Returns:
    - components: Detected tags (e.g. V-101, PT-202, Pump-A).
    - instruments: Detected sensor/transmitter codes (PT, TT, FT, etc.).
    - annotations: Extracted notes and drawing specifications.
    - connections: Inferred piping or line references.
    - low_confidence_regions: Any ambiguous labels flagged for safety.
    """
    raw_bytes = _ensure_bytes(image_input)

    # Preprocess & Run OCR
    if _PIL_AVAILABLE and Image is not None:
        try:
            img = Image.open(io.BytesIO(raw_bytes))
        except Exception as e:
            return {'status': 'error', 'message': f'Cannot parse image: {e}'}
        preprocessed = _pil_preprocess(img)
        buf = io.BytesIO()
        preprocessed.save(buf, format="PNG")
        proc_bytes = buf.getvalue()
    else:
        proc_bytes = raw_bytes

    ocr_result = run_ocr(proc_bytes)
    text = ocr_result.get("text", "") if ocr_result.get("status") == "ok" else ""
    words = ocr_result.get("words", [])

    components = []
    instruments = []
    annotations = []

    # Map words to components and instruments with bounding boxes
    for w in words:
        val = w.get("text", "").strip()
        bbox = w.get("bbox", {})
        conf = w.get("confidence", 1.0)

        # Check for P&ID tag matches (e.g., V-101, P-102, FT-301)
        if _PID_TAG_PATTERN.match(val):
            prefix = re.split(r"[-_0-9]", val)[0].upper()
            if prefix in _INSTRUMENT_PREFIXES:
                instruments.append({
                    "tag": val,
                    "type": "instrument",
                    "prefix": prefix,
                    "confidence": conf,
                    "bbox": bbox
                })
            else:
                components.append({
                    "tag": val,
                    "type": "component",
                    "confidence": conf,
                    "bbox": bbox
                })
        elif len(val) > 4:
            annotations.append({
                "text": val,
                "confidence": conf,
                "bbox": bbox
            })

    low_conf_flags = flag_low_confidence_regions(ocr_result, threshold=0.70)

    return {
        "status": "ok",
        "document_type": "engineering_drawing",
        "diagram_summary": f"Detected {len(components)} equipment component(s) and {len(instruments)} instrument(s).",
        "components": components,
        "instruments": instruments,
        "annotations": annotations[:25],  # Top annotations
        "full_text": text,
        "total_tags": len(components) + len(instruments),
        "average_confidence": ocr_result.get("average_confidence", 0.0),
        "low_confidence_regions": low_conf_flags,
        "image_size": ocr_result.get("image_size", {})
    }


def generate_visual_evidence(image_input: bytes | str, bbox: dict, label: str = "") -> dict:
    """
    Generates a cropped image region as visual evidence proof for citations.
    Returns base64 encoded PNG thumbnail and bounding metadata.
    """
    raw_bytes = _ensure_bytes(image_input)
    cropped_bytes = crop_image_region(raw_bytes, bbox)
    b64_img = base64.b64encode(cropped_bytes).decode("utf-8")

    return {
        "status": "ok",
        "label": label,
        "bbox": bbox,
        "thumbnail_b64": f"data:image/png;base64,{b64_img}",
        "size_bytes": len(cropped_bytes)
    }


def process_multimodal_task(image_input: bytes | str, task_type: str = "auto") -> dict:
    """
    Unified entry point for multimodal tasks:
    1. Auto-classifies image type if not explicitly specified.
    2. Runs structured extraction pipeline.
    3. Formats grounding JSON for downstream reasoning models.
    """
    raw_bytes = _ensure_bytes(image_input)

    if task_type == "auto":
        detected_type = classify_image_type(raw_bytes)
    else:
        detected_type = task_type

    if detected_type == "engineering_drawing":
        result = analyze_engineering_drawing(raw_bytes)
    else:
        result = analyze_scanned_document(raw_bytes)

    # Attach anti-hallucination summary prompt for LLM consumption
    grounding_summary = (
        f"--- GROUNDED VISUAL EXTRACTION ({result.get('document_type')}) ---\n"
        f"Average OCR Confidence: {int(result.get('average_confidence', 0.0) * 100)}%\n"
        f"Flagged Low-Confidence Regions: {len(result.get('low_confidence_regions', []))}\n"
    )

    if result.get("document_type") == "scanned_document":
        if result.get("key_values"):
            grounding_summary += "Key-Value Pairs:\n" + "\n".join(f"  * {k}: {v}" for k, v in result["key_values"].items()) + "\n"
        grounding_summary += f"Extracted Text:\n{result.get('full_text', '')[:2000]}"
    else:
        grounding_summary += f"Summary: {result.get('diagram_summary', '')}\n"
        grounding_summary += "Components: " + ", ".join(c.get("tag", "") for c in result.get("components", [])) + "\n"
        grounding_summary += "Instruments: " + ", ".join(i.get("tag", "") for i in result.get("instruments", [])) + "\n"
        grounding_summary += f"Extracted Text:\n{result.get('full_text', '')[:2000]}"

    result["grounding_prompt"] = grounding_summary
    return result
