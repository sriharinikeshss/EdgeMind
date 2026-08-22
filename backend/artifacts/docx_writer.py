"""
DOCX Artifact Writer — Phase 7 implementation (M5).

Uses python-docx to build real documents with headings, paragraphs,
tables, and an appended citations block sourced from RAG metadata.
"""
from __future__ import annotations
import uuid
from typing import Any

from docx import Document

from artifacts.storage import artifact_path, sha256_file
from artifacts.citations import format_citation_line

CONTENT_TYPE = "application/vnd.openxmlformats-officedocument.wordprocessingml.document"


class DocxWriter:
    """Writes task outputs to real .docx files, hashed and stored on disk."""

    def add_heading(self, doc: Document, text: str, level: int = 1) -> None:
        doc.add_heading(text, level=level)

    def add_table(self, doc: Document, headers: list[str], rows: list[list[Any]]) -> None:
        table = doc.add_table(rows=1, cols=len(headers))
        try:
            table.style = "Light Grid Accent 1"
        except KeyError:
            pass  # style not available in a minimal template — fall back to default grid
        header_cells = table.rows[0].cells
        for i, header in enumerate(headers):
            header_cells[i].text = str(header)
        for row in rows:
            row_cells = table.add_row().cells
            for i, value in enumerate(row):
                row_cells[i].text = str(value)

    def add_citations(self, doc: Document, citations: list[dict | str]) -> None:
        """Append a 'References' section. Accepts either citation shape —
        {"doc_id"/"source": ..., "text": ..., "page": ...} — via normalize_citation()."""
        self.add_heading(doc, "References", level=2)
        for i, citation in enumerate(citations, start=1):
            doc.add_paragraph(format_citation_line(i, citation))

    def apply_template(self, doc: Document, template_path: str) -> Document:
        """Load a corporate .docx template as the base document instead of a blank one."""
        return Document(template_path)

    def create_docx(
        self,
        task_id: str,
        title: str,
        content: str,
        table: dict | None = None,
        citations: list[dict | str] | None = None,
        template_path: str | None = None,
        filename: str | None = None,
    ) -> dict:
        """
        Build a DOCX artifact and persist it to disk.

        `table`, if given, is {"headers": [...], "rows": [[...], ...]}.
        Returns artifact metadata: id, filename, content_type, file_hash, path.
        """
        artifact_id = str(uuid.uuid4())
        filename = filename or f"{_slugify(title)}.docx"

        doc = self.apply_template(None, template_path) if template_path else Document()
        self.add_heading(doc, title, level=1)

        for paragraph in content.split("\n\n"):
            paragraph = paragraph.strip()
            if paragraph:
                doc.add_paragraph(paragraph)

        if table and table.get("headers"):
            self.add_table(doc, table["headers"], table.get("rows", []))

        if citations:
            self.add_citations(doc, citations)

        path = artifact_path(task_id, artifact_id, filename)
        doc.save(path)
        file_hash = self.calculate_artifact_hash(path)

        return {
            "status": "ok",
            "id": artifact_id,
            "task_id": task_id,
            "filename": filename,
            "content_type": CONTENT_TYPE,
            "file_hash": file_hash,
            "path": path,
        }

    def save_artifact(self, doc: Document, path: str) -> str:
        """Save an in-memory Document to `path` and return its SHA-256 hash."""
        doc.save(path)
        return self.calculate_artifact_hash(path)

    def calculate_artifact_hash(self, path: str) -> str:
        return sha256_file(path)


def _slugify(title: str) -> str:
    slug = "".join(c if c.isalnum() else "_" for c in title.strip()) or "artifact"
    return slug[:50]
