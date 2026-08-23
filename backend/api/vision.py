"""
Vision & Multimodal API ΓÇö Phase 3 & 5 implementations (M4).

Endpoints:
- POST /api/vision/analyze: Basic OCR text & confidence extraction.
- POST /api/vision/multimodal: Full structured extraction (scanned documents, P&ID drawings) with low-confidence anti-hallucination flags.
- POST /api/vision/evidence: Crop & return visual evidence proof snippets.
"""
from __future__ import annotations
import base64
import logging
from fastapi import APIRouter, Depends
from pydantic import BaseModel, Field

from ocr.processor import run_ocr, calculate_ocr_confidence
from ocr.preprocess import _pil_preprocess
from vision.multimodal_processor import (
    process_multimodal_task,
    generate_visual_evidence,
    classify_image_type
)
from security.rbac import require_any_role
from api.auth import UserInfo

logger = logging.getLogger(__name__)
router = APIRouter()


class VisionAnalyzeRequest(BaseModel):
    image_base64: str | None = None
    image_path: str | None = None
    hint: str | None = None


class VisionAnalyzeResponse(BaseModel):
    status: str
    text: str
    confidence: float
    message: str | None = None


class MultimodalProcessRequest(BaseModel):
    image_base64: str | None = None
    image_path: str | None = None
    task_type: str = "auto"   # auto | scanned_document | engineering_drawing


class MultimodalProcessResponse(BaseModel):
    status: str
    document_type: str
    average_confidence: float = 0.0
    low_confidence_regions: list[dict] = Field(default_factory=list)
    key_values: dict[str, str] = Field(default_factory=dict)
    components: list[dict] = Field(default_factory=list)
    instruments: list[dict] = Field(default_factory=list)
    full_text: str = ""
    grounding_prompt: str = ""
    message: str | None = None


class VisualEvidenceRequest(BaseModel):
    image_base64: str | None = None
    image_path: str | None = None
    bbox: dict                 # {"x": int, "y": int, "w": int, "h": int}
    label: str = ""


class VisualEvidenceResponse(BaseModel):
    status: str
    label: str = ""
    bbox: dict = Field(default_factory=dict)
    thumbnail_b64: str = ""
    message: str | None = None


def _get_image_bytes(image_base64: str | None, image_path: str | None) -> bytes:
    if image_base64:
        is_pdf = "application/pdf" in image_base64
        # Strip data URL prefix if present
        if "," in image_base64:
            image_base64 = image_base64.split(",", 1)[1]
        
        raw_bytes = base64.b64decode(image_base64)
        
        if is_pdf:
            try:
                import fitz  # PyMuPDF
                doc = fitz.open("pdf", raw_bytes)
                page = doc.load_page(0)
                pix = page.get_pixmap(dpi=300)
                raw_bytes = pix.tobytes("png")
            except Exception as e:
                logger.error("Failed to convert PDF to image: %s", e)
                raise ValueError(f"Failed to convert PDF: {e}")
                
        return raw_bytes
    elif image_path:
        with open(image_path, "rb") as f:
            return f.read()
    raise ValueError("Provide either image_base64 or image_path.")


@router.post("/vision/analyze", response_model=VisionAnalyzeResponse)
def analyze_vision(req: VisionAnalyzeRequest, current_user: UserInfo = Depends(require_any_role)):
    """
    Standalone basic OCR endpoint.
    """
    try:
        image_bytes = _get_image_bytes(req.image_base64, req.image_path)
    except Exception as exc:
        return VisionAnalyzeResponse(status="error", text="", confidence=0.0, message=str(exc))

    ocr_res = run_ocr(image_bytes)
    if ocr_res.get("status") != "ok":
        return VisionAnalyzeResponse(status="error", text="", confidence=0.0, message=ocr_res.get("message"))

    conf = ocr_res.get("average_confidence", calculate_ocr_confidence(ocr_res))
    return VisionAnalyzeResponse(
        status="ok",
        text=ocr_res.get("text", ""),
        confidence=round(conf, 4)
    )


@router.post("/vision/multimodal", response_model=MultimodalProcessResponse)
def process_multimodal(req: MultimodalProcessRequest, current_user: UserInfo = Depends(require_any_role)):
    """
    Phase 5: Full multimodal analysis for scanned documents and P&ID engineering drawings.
    """
    try:
        image_bytes = _get_image_bytes(req.image_base64, req.image_path)
    except Exception as exc:
        return MultimodalProcessResponse(status="error", document_type="unknown", message=str(exc))

    result = process_multimodal_task(image_bytes, task_type=req.task_type)
    return MultimodalProcessResponse(
        status=result.get("status", "ok"),
        document_type=result.get("document_type", "unknown"),
        average_confidence=result.get("average_confidence", 0.0),
        low_confidence_regions=result.get("low_confidence_regions", []),
        key_values=result.get("key_values", {}),
        components=result.get("components", []),
        instruments=result.get("instruments", []),
        full_text=result.get("full_text", ""),
        grounding_prompt=result.get("grounding_prompt", ""),
        message=result.get("message")
    )


@router.post("/vision/evidence", response_model=VisualEvidenceResponse)
def get_visual_evidence(req: VisualEvidenceRequest, current_user: UserInfo = Depends(require_any_role)):
    """
    Phase 5: Generate cropped thumbnail evidence for a given bounding box.
    """
    try:
        image_bytes = _get_image_bytes(req.image_base64, req.image_path)
        evidence = generate_visual_evidence(image_bytes, req.bbox, label=req.label)
        return VisualEvidenceResponse(
            status="ok",
            label=evidence.get("label", req.label),
            bbox=evidence.get("bbox", req.bbox),
            thumbnail_b64=evidence.get("thumbnail_b64", "")
        )
    except Exception as exc:
        return VisualEvidenceResponse(status="error", message=str(exc))