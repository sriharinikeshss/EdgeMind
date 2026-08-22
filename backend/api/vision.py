"""
POST /api/vision/analyze — Phase 3 M4 standalone vision/OCR endpoint.

Accepts a base64-encoded image, preprocesses it, runs Tesseract OCR,
and returns extracted text with confidence score.
"""
import base64
import logging
from fastapi import APIRouter
from pydantic import BaseModel

from ocr.preprocess import preprocess_image as _preprocess_bytes
from ocr.processor import run_ocr, calculate_ocr_confidence

logger = logging.getLogger(__name__)
router = APIRouter()


class VisionAnalyzeRequest(BaseModel):
    image_base64: str          # base64-encoded image bytes
    image_path: str | None = None   # alternative: path to image on disk
    hint: str | None = None    # optional hint about what to look for


class VisionAnalyzeResponse(BaseModel):
    status: str
    text: str
    confidence: float
    message: str | None = None


def _preprocess_from_bytes(image_bytes: bytes) -> dict:
    """Run Pillow preprocessing on raw bytes (no file path)."""
    import io
    try:
        from PIL import Image, ImageOps, ImageFilter
        img = Image.open(io.BytesIO(image_bytes))
        img = img.convert("L")
        img = ImageOps.autocontrast(img, cutoff=2)
        img = img.filter(ImageFilter.SHARPEN)
        buf = io.BytesIO()
        img.save(buf, format="PNG")
        return {
            "status": "ok",
            "image_bytes": buf.getvalue(),
        }
    except Exception as exc:
        return {"status": "error", "message": str(exc)}


@router.post("/vision/analyze", response_model=VisionAnalyzeResponse)
def analyze_vision(req: VisionAnalyzeRequest):
    """
    Phase 3 M4: standalone vision analysis endpoint.
    Accepts a base64 image, preprocesses, runs OCR, returns text + confidence.
    """
    # Decode image
    if req.image_base64:
        try:
            image_bytes = base64.b64decode(req.image_base64)
        except Exception as exc:
            return VisionAnalyzeResponse(
                status="error",
                text="",
                confidence=0.0,
                message=f"Base64 decode failed: {exc}",
            )
    elif req.image_path:
        try:
            with open(req.image_path, "rb") as f:
                image_bytes = f.read()
        except Exception as exc:
            return VisionAnalyzeResponse(
                status="error",
                text="",
                confidence=0.0,
                message=f"File read failed: {exc}",
            )
    else:
        return VisionAnalyzeResponse(
            status="error",
            text="",
            confidence=0.0,
            message="Provide either image_base64 or image_path.",
        )

    # Preprocess
    preprocessed = _preprocess_from_bytes(image_bytes)
    if preprocessed["status"] != "ok":
        return VisionAnalyzeResponse(
            status="error",
            text="",
            confidence=0.0,
            message=preprocessed.get("message", "Preprocessing failed"),
        )

    # OCR
    ocr_result = run_ocr(preprocessed["image_bytes"])
    if ocr_result["status"] != "ok":
        return VisionAnalyzeResponse(
            status="error",
            text="",
            confidence=0.0,
            message=ocr_result.get("message", "OCR failed"),
        )

    confidence = calculate_ocr_confidence(ocr_result)
    return VisionAnalyzeResponse(
        status="ok",
        text=ocr_result.get("text", ""),
        confidence=round(confidence, 4),
    )
