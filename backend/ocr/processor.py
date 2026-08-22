"""
Phase 2: OCR processing.
Runs Tesseract OCR on a given image.
"""
import io
try:
    from PIL import Image
except ImportError:
    Image = None

def run_ocr(image_bytes: bytes) -> dict:
    """
    Run Tesseract OCR on the preprocessed image bytes.
    Returns parsed text and data.
    """
    try:
        import pytesseract
    except ImportError:
        return {"status": "error", "message": "pytesseract not installed."}

    if not Image:
        return {"status": "error", "message": "Pillow not installed."}

    try:
        img = Image.open(io.BytesIO(image_bytes))
        
        # Get raw text
        text = pytesseract.image_to_string(img)
        
        # Get detailed data (includes confidences)
        data = pytesseract.image_to_data(img, output_type=pytesseract.Output.DICT)
        
        return {
            "status": "ok",
            "text": text.strip(),
            "data": data,
        }
    except Exception as e:
        return {"status": "error", "message": str(e)}

def calculate_ocr_confidence(ocr_result: dict) -> float:
    """
    Parse confidence scores from Tesseract output and return an aggregate confidence.
    """
    if ocr_result.get("status") != "ok" or "data" not in ocr_result:
        return 0.0
    
    data = ocr_result["data"]
    confidences = [int(c) for c in data.get("conf", []) if str(c).isdigit() and int(c) >= 0]
    
    if not confidences:
        return 0.0

    return sum(confidences) / len(confidences) / 100.0  # Normalized to 0.0 - 1.0


def flag_low_confidence_regions(ocr_result: dict, threshold: float = 0.6) -> list[dict]:
    """
    Phase 5: parse per-word confidence + bounding boxes from Tesseract output
    and return the words below `threshold`, so they can be surfaced to the
    user instead of silently trusted (anti-hallucination requirement).
    """
    if ocr_result.get("status") != "ok" or "data" not in ocr_result:
        return []

    data = ocr_result["data"]
    texts = data.get("text", [])
    confs = data.get("conf", [])
    lefts = data.get("left", [])
    tops = data.get("top", [])
    widths = data.get("width", [])
    heights = data.get("height", [])

    flagged = []
    for text, conf, left, top, width, height in zip(texts, confs, lefts, tops, widths, heights):
        if not text or not text.strip():
            continue
        if not str(conf).lstrip("-").isdigit():
            continue
        conf_int = int(conf)
        if conf_int < 0:
            continue
        conf_norm = conf_int / 100.0
        if conf_norm < threshold:
            flagged.append({
                "text": text,
                "confidence": round(conf_norm, 4),
                "bbox": [left, top, width, height],
            })

    return flagged
