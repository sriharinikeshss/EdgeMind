"""
Document parsers — Phase 6 (M3).

Format-specific text extraction for the document ingestion pipeline.
Each parser returns a clean {"status": "error", "message": ...} on failure
instead of letting a raw library exception (which can leak internal object
reprs, matching what Phase 5's OCR work already ran into) reach the caller.
"""
from __future__ import annotations
import io
import logging
import re

logger = logging.getLogger(__name__)

_OBJECT_REPR_RE = re.compile(r"<[\w.]+ object at 0x[0-9a-fA-F]+>")


def _safe_error_message(exc: Exception) -> str:
    """
    Strip internal Python object reprs (e.g. "<...BytesIO object at 0x...>")
    out of an exception message before it reaches the user. Kept local
    rather than imported from ocr.preprocess — that module is owned by a
    different, currently actively-changing part of the codebase, and this
    sanitizer is generic enough not to need a cross-module dependency on it.
    """
    return _OBJECT_REPR_RE.sub("<file>", str(exc))


def parse_pdf(file_bytes: bytes) -> dict:
    """
    Extract text per page from a PDF.
    Returns {"status": "ok", "pages": [{"page": int, "text": str}, ...]}
    or {"status": "error", "message": str}.
    """
    try:
        from pypdf import PdfReader
    except ImportError:
        return {"status": "error", "message": "pypdf not installed."}

    try:
        reader = PdfReader(io.BytesIO(file_bytes))
        pages = []
        for i, page in enumerate(reader.pages):
            text = (page.extract_text() or "").strip()
            pages.append({"page": i + 1, "text": text})
        return {"status": "ok", "pages": pages}
    except Exception as exc:
        logger.error("parse_pdf failed: %s", exc)
        return {"status": "error", "message": _safe_error_message(exc)}


def parse_docx(file_bytes: bytes) -> dict:
    """
    Extract text from a DOCX file. DOCX has no native page concept, so all
    text comes back as a single "page" (page=None) — page-level citations
    aren't meaningful for this format.
    Returns {"status": "ok", "pages": [{"page": None, "text": str}]}
    or {"status": "error", "message": str}.
    """
    try:
        import docx
    except ImportError:
        return {"status": "error", "message": "python-docx not installed."}

    try:
        document = docx.Document(io.BytesIO(file_bytes))
        text = "\n".join(p.text for p in document.paragraphs if p.text.strip())
        return {"status": "ok", "pages": [{"page": None, "text": text}]}
    except Exception as exc:
        logger.error("parse_docx failed: %s", exc)
        return {"status": "error", "message": _safe_error_message(exc)}


def parse_txt(file_bytes: bytes) -> dict:
    """
    Decode a plain-text/markdown file. Returns the same {"pages": [...]}
    shape as the other parsers for a uniform ingest_document() call site.
    """
    try:
        text = file_bytes.decode("utf-8", errors="replace")
        return {"status": "ok", "pages": [{"page": None, "text": text}]}
    except Exception as exc:
        logger.error("parse_txt failed: %s", exc)
        return {"status": "error", "message": _safe_error_message(exc)}


# Extension -> parser function
_PARSERS = {
    ".pdf": parse_pdf,
    ".docx": parse_docx,
    ".txt": parse_txt,
    ".md": parse_txt,
}


def parse_document(filename: str, file_bytes: bytes) -> dict:
    """
    Dispatch to the right parser based on filename extension.
    Returns {"status": "error", "message": ...} for unsupported extensions.
    """
    import os
    ext = os.path.splitext(filename)[1].lower()
    parser = _PARSERS.get(ext)
    if not parser:
        supported = ", ".join(sorted(_PARSERS.keys()))
        return {"status": "error", "message": f"Unsupported file type '{ext}'. Supported: {supported}"}
    return parser(file_bytes)
