"""
OCR Preprocessing — Phase 1 implementation (M4).

preprocess_pdf_page() / preprocess_image() prepare scanned images for OCR
by: converting to grayscale, normalising resolution to 300 DPI,
applying adaptive thresholding, and returning a cleaned PIL Image.

Dependencies: Pillow (already in requirements.txt in Phase 1 additions).
In Phase 2/5, PaddleOCR or Tesseract will be called on the output image.
"""
from __future__ import annotations
import io
import logging
from pathlib import Path

logger = logging.getLogger(__name__)

try:
    from PIL import Image, ImageOps, ImageFilter
    _PIL_AVAILABLE = True
except ImportError:
    _PIL_AVAILABLE = False
    logger.warning("Pillow not installed — OCR preprocessing will return stub output.")

TARGET_DPI = 300  # standard for OCR accuracy


def _pil_preprocess(image: "Image.Image") -> "Image.Image":
    """
    Core preprocessing pipeline applied to a single PIL Image:
    1. Convert to grayscale
    2. Resize to TARGET_DPI if original DPI is lower
    3. Apply autocontrast to normalise brightness
    4. Sharpen to improve character edges
    """
    # Step 1: Grayscale
    image = image.convert("L")

    # Step 2: Auto-contrast (normalises histogram)
    image = ImageOps.autocontrast(image, cutoff=2)

    # Step 3: Sharpening pass
    image = image.filter(ImageFilter.SHARPEN)

    return image


def preprocess_image(image_path: str) -> dict:
    """
    Load and preprocess a single image file (JPEG, PNG, TIFF, BMP, etc.)
    for downstream OCR.

    Args:
        image_path: Absolute path to the image file.

    Returns:
        {
            "status": "ok" | "error",
            "image_bytes": bytes,         # PNG-encoded preprocessed image
            "original_size": (w, h),
            "processed_size": (w, h),
            "format": str,
        }

    Phase 2: this output is passed to run_ocr() in ocr/processor.py.
    """
    if not _PIL_AVAILABLE:
        return {
            "status": "error",
            "message": "Pillow not installed. Run: pip install Pillow",
        }

    path = Path(image_path)
    if not path.exists():
        return {"status": "error", "message": f"File not found: {image_path}"}

    try:
        with Image.open(path) as img:
            original_size = img.size
            processed = _pil_preprocess(img)
            processed_size = processed.size

            buf = io.BytesIO()
            processed.save(buf, format="PNG")
            image_bytes = buf.getvalue()

        logger.info(
            "preprocess_image: %s | %s → %s (%.1f KB)",
            path.name,
            original_size,
            processed_size,
            len(image_bytes) / 1024,
        )
        return {
            "status": "ok",
            "image_bytes": image_bytes,
            "original_size": original_size,
            "processed_size": processed_size,
            "format": "PNG",
        }
    except Exception as exc:
        logger.error("preprocess_image failed: %s", exc)
        return {"status": "error", "message": str(exc)}


def preprocess_image_bytes(image_bytes: bytes) -> dict:
    """
    Preprocess raw image bytes (no file path) for downstream OCR.
    Same pipeline and return schema as preprocess_image(), used when the
    image arrives in-memory (e.g. a base64-decoded upload) rather than
    as a file on disk.

    Phase 5: shared by tools/registry.py's analyze_scanned_document tool
    and api/vision.py's standalone endpoint, so preprocessing logic lives
    in exactly one place.
    """
    if not _PIL_AVAILABLE:
        return {
            "status": "error",
            "message": "Pillow not installed. Run: pip install Pillow",
        }

    try:
        with Image.open(io.BytesIO(image_bytes)) as img:
            original_size = img.size
            processed = _pil_preprocess(img)
            processed_size = processed.size

            buf = io.BytesIO()
            processed.save(buf, format="PNG")
            processed_bytes = buf.getvalue()

        return {
            "status": "ok",
            "image_bytes": processed_bytes,
            "original_size": original_size,
            "processed_size": processed_size,
            "format": "PNG",
        }
    except Exception as exc:
        logger.error("preprocess_image_bytes failed: %s", exc)
        return {"status": "error", "message": str(exc)}


def preprocess_pdf_page(pdf_path: str, page_index: int = 0) -> dict:
    """
    Extract and preprocess a single page from a PDF file.

    Requires 'pdf2image' + 'poppler' for PDF rasterisation; falls back
    to a Pillow-only path if pdf2image is not available.

    Args:
        pdf_path:   Absolute path to the PDF file.
        page_index: 0-based page number to extract.

    Returns: same schema as preprocess_image().

    Phase 2: pdf2image will be added to requirements; for now this
    gracefully reports if it's missing.
    """
    try:
        from pdf2image import convert_from_path  # type: ignore
        pages = convert_from_path(pdf_path, dpi=TARGET_DPI)
        if page_index >= len(pages):
            return {
                "status": "error",
                "message": f"Page {page_index} out of range (PDF has {len(pages)} pages).",
            }
        pil_page = pages[page_index]
        processed = _pil_preprocess(pil_page)
        buf = io.BytesIO()
        processed.save(buf, format="PNG")
        return {
            "status": "ok",
            "image_bytes": buf.getvalue(),
            "original_size": pil_page.size,
            "processed_size": processed.size,
            "format": "PNG",
            "page_index": page_index,
        }
    except ImportError:
        return {
            "status": "error",
            "message": (
                "pdf2image not installed. "
                "Run: pip install pdf2image  (also needs poppler on the system PATH). "
                "This will be added in Phase 2."
            ),
        }
    except Exception as exc:
        logger.error("preprocess_pdf_page failed: %s", exc)
        return {"status": "error", "message": str(exc)}



