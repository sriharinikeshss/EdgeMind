"""
Artifact format validators — Phase 8 implementation (M5).

validate_artifact() is the gate every generated artifact must pass before its
step is accepted as successful (see Executor.execute_step's ARTIFACT_TOOL_NAMES
branch): file-integrity (hash match) + a format-specific structural check
(+ an optional required-sections check for document-style formats).

Reuses Phase 7's writers/storage — this module only reads back what they wrote.
"""
from __future__ import annotations
import csv
import json
import logging
import os

from artifacts.storage import sha256_file

logger = logging.getLogger(__name__)

_XLSX_FORMULA_ERRORS = {"#REF!", "#VALUE!", "#DIV/0!", "#NAME?", "#N/A", "#NULL!", "#NUM!"}


def validate_file_integrity(path: str, expected_hash: str | None) -> dict:
    """DoD: artifact hash reproducibly verifies file integrity."""
    if not os.path.isfile(path):
        return {"valid": False, "errors": ["file missing on disk"]}
    if expected_hash:
        actual = sha256_file(path)
        if actual != expected_hash:
            return {"valid": False, "errors": [f"hash mismatch: expected {expected_hash}, got {actual}"]}
    return {"valid": True, "errors": []}


def validate_required_sections(text: str, required_sections: list[str]) -> dict:
    missing = [s for s in required_sections if s.lower() not in (text or "").lower()]
    return {"valid": not missing, "errors": [f"missing section: {m}" for m in missing], "missing": missing}


def validate_docx(path: str) -> dict:
    try:
        from docx import Document
        doc = Document(path)
        if not (doc.paragraphs or doc.tables):
            return {"valid": False, "errors": ["document has no paragraphs or tables"]}
        return {"valid": True, "errors": []}
    except Exception as exc:
        return {"valid": False, "errors": [f"corrupt or unreadable docx: {exc}"]}


def validate_xlsx(path: str) -> dict:
    """Structural check + formula-error-string detection (#REF!, #DIV/0!, ...)."""
    try:
        from openpyxl import load_workbook
        wb = load_workbook(path)
        errors = []
        any_data = False
        for ws in wb.worksheets:
            for row in ws.iter_rows():
                for cell in row:
                    if cell.value is None:
                        continue
                    any_data = True
                    if isinstance(cell.value, str) and cell.value.strip().upper() in _XLSX_FORMULA_ERRORS:
                        errors.append(f"formula error {cell.value} at {ws.title}!{cell.coordinate}")
        if not any_data:
            errors.append("workbook has no data")
        return {"valid": not errors, "errors": errors}
    except Exception as exc:
        return {"valid": False, "errors": [f"corrupt or unreadable xlsx: {exc}"]}


def validate_pdf(path: str) -> dict:
    try:
        with open(path, "rb") as f:
            header = f.read(5)
        if header != b"%PDF-":
            return {"valid": False, "errors": ["missing %PDF- header"]}
        from pypdf import PdfReader
        reader = PdfReader(path)
        if len(reader.pages) == 0:
            return {"valid": False, "errors": ["PDF has zero pages"]}
        return {"valid": True, "errors": []}
    except Exception as exc:
        return {"valid": False, "errors": [f"corrupt or unreadable pdf: {exc}"]}


def validate_csv(path: str) -> dict:
    try:
        with open(path, newline="", encoding="utf-8") as f:
            rows = list(csv.reader(f))
        if not rows:
            return {"valid": False, "errors": ["csv file is empty"]}
        return {"valid": True, "errors": []}
    except Exception as exc:
        return {"valid": False, "errors": [f"corrupt or unreadable csv: {exc}"]}


def validate_json(path: str) -> dict:
    try:
        with open(path, encoding="utf-8") as f:
            json.load(f)
        return {"valid": True, "errors": []}
    except Exception as exc:
        return {"valid": False, "errors": [f"corrupt or unreadable json: {exc}"]}


_VALIDATORS_BY_EXT = {
    ".docx": validate_docx,
    ".xlsx": validate_xlsx,
    ".pdf": validate_pdf,
    ".csv": validate_csv,
    ".json": validate_json,
}


def validate_artifact(artifact_meta: dict, required_sections: list[str] | None = None) -> dict:
    """
    DoD: no artifact reaches COMPLETED without passing its format-specific validator.

    `artifact_meta` is the dict returned by a Phase 7 writer (create_docx/xlsx/pdf/csv/json):
    must include `path`; `file_hash` and `filename` are used when present.
    """
    path = artifact_meta.get("path")
    if not path:
        return {"valid": False, "errors": ["no artifact path to validate"]}

    integrity = validate_file_integrity(path, artifact_meta.get("file_hash"))
    if not integrity["valid"]:
        return integrity

    ext = os.path.splitext(artifact_meta.get("filename") or path)[1].lower()
    checker = _VALIDATORS_BY_EXT.get(ext)
    if not checker:
        return {"valid": True, "errors": [], "note": f"no format validator for {ext}, integrity check only"}

    result = checker(path)

    if result["valid"] and required_sections and ext in (".docx", ".pdf"):
        section_check = validate_required_sections(_extract_text(path, ext), required_sections)
        if not section_check["valid"]:
            return section_check

    return result


def _extract_text(path: str, ext: str) -> str:
    try:
        if ext == ".docx":
            from docx import Document
            return "\n".join(p.text for p in Document(path).paragraphs)
        if ext == ".pdf":
            from pypdf import PdfReader
            return "\n".join((page.extract_text() or "") for page in PdfReader(path).pages)
    except Exception as exc:
        logger.warning("Text extraction failed for %s: %s", path, exc)
    return ""
