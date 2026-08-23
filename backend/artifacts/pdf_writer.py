"""
PDF Artifact Writer — Phase 7 implementation (M5).

Uses reportlab to build a simple structured report: title, body
paragraphs, an optional table, and a citations block.
"""
from __future__ import annotations
import uuid
from typing import Any

from reportlab.lib import colors
from reportlab.lib.pagesizes import A4
from reportlab.lib.styles import getSampleStyleSheet
from reportlab.platypus import SimpleDocTemplate, Paragraph, Spacer, Table, TableStyle

from artifacts.storage import artifact_path, sha256_file
from artifacts.citations import format_citation_line

CONTENT_TYPE = "application/pdf"


class PdfWriter:
    """Writes task outputs to real .pdf files, hashed and stored on disk."""

    def create_pdf(
        self,
        task_id: str,
        title: str,
        content: str,
        table: dict | None = None,
        citations: list[dict | str] | None = None,
        filename: str | None = None,
    ) -> dict:
        """Build a PDF artifact and persist it to disk."""
        artifact_id = str(uuid.uuid4())
        filename = filename or f"{_slugify(title)}.pdf"
        path = artifact_path(task_id, artifact_id, filename)

        styles = getSampleStyleSheet()
        doc = SimpleDocTemplate(path, pagesize=A4)
        story: list[Any] = [Paragraph(title, styles["Title"]), Spacer(1, 12)]

        for paragraph in content.split("\n\n"):
            paragraph = paragraph.strip()
            if paragraph:
                story.append(Paragraph(paragraph, styles["BodyText"]))
                story.append(Spacer(1, 8))

        if table and table.get("headers"):
            data = [table["headers"]] + table.get("rows", [])
            grid = Table(data)
            grid.setStyle(TableStyle([
                ("BACKGROUND", (0, 0), (-1, 0), colors.lightgrey),
                ("GRID", (0, 0), (-1, -1), 0.5, colors.grey),
                ("FONTNAME", (0, 0), (-1, 0), "Helvetica-Bold"),
            ]))
            story.append(grid)
            story.append(Spacer(1, 12))

        if citations:
            # Accepts either citation shape via format_citation_line() — see artifacts/citations.py.
            story.append(Paragraph("References", styles["Heading2"]))
            for i, citation in enumerate(citations, start=1):
                story.append(Paragraph(format_citation_line(i, citation), styles["BodyText"]))

        doc.build(story)
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

    def calculate_artifact_hash(self, path: str) -> str:
        return sha256_file(path)


def _slugify(title: str) -> str:
    slug = "".join(c if c.isalnum() else "_" for c in title.strip()) or "artifact"
    return slug[:50]
