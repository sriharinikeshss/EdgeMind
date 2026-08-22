"""
DOCX Artifact Writer — Phase 0 scaffold (M5).

In Phase 7, create_docx() will use python-docx to build real documents
with tables, headings, and embedded citations.
"""
from __future__ import annotations
from pathlib import Path


class DocxWriter:
    """
    Writes task outputs to .docx files.

    Phase 0: stub signatures.
    Phase 7: full python-docx implementation.
    """

    def create_docx(
        self,
        task_id: str,
        title: str,
        content: str,
        output_dir: str | Path = "/tmp/artifacts",
    ) -> Path:
        """
        Build and save a DOCX file.
        Returns the path to the saved file.
        TODO Phase 7.
        """
        raise NotImplementedError("DOCX generation implemented in Phase 7.")

    def add_table(self, doc, headers: list[str], rows: list[list[str]]) -> None:
        """TODO Phase 7: add a formatted table to an open Document object."""
        raise NotImplementedError("Table helper implemented in Phase 7.")

    def add_heading(self, doc, text: str, level: int = 1) -> None:
        """TODO Phase 7."""
        raise NotImplementedError("Heading helper implemented in Phase 7.")

    def add_citations(self, doc, citations: list[dict]) -> None:
        """TODO Phase 7: append citation block from RAG metadata."""
        raise NotImplementedError("Citation block implemented in Phase 7.")

    def apply_template(self, doc, template_path: str | Path) -> None:
        """TODO Phase 7: apply a corporate DOCX template."""
        raise NotImplementedError("Template application implemented in Phase 7.")

    def save_artifact(self, doc, path: str | Path) -> str:
        """TODO Phase 7: save document and return SHA-256 hash."""
        raise NotImplementedError("Artifact saving implemented in Phase 7.")

    def calculate_artifact_hash(self, path: str | Path) -> str:
        """TODO Phase 7: compute SHA-256 of the artifact file."""
        raise NotImplementedError("Artifact hash implemented in Phase 7.")
