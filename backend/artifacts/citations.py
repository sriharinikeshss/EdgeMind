"""
Citation normalization — Phase 7 (shared by all artifact writers).

RAG citation payloads have shown up in two shapes across branches:
  - the current rag/retrieval.py chunk shape: {"doc_id": ..., "text": ...}
  - the incoming Phase 6 payload: {"source": ..., "text": ..., "page": ...}

normalize_citation() accepts either (or a bare string) and returns a single
consistent dict so every writer's References section renders the same way
regardless of which upstream shape produced it.
"""
from __future__ import annotations


def normalize_citation(citation: dict | str) -> dict:
    """Return {"source": str, "text": str, "page": int | None} for one citation."""
    if isinstance(citation, dict):
        source = citation.get("source") or citation.get("doc_id") or "Unknown"
        return {
            "source": source,
            "text": citation.get("text", ""),
            "page": citation.get("page"),
        }
    return {"source": "Unknown", "text": str(citation), "page": None}


def format_citation_line(index: int, citation: dict | str) -> str:
    """Render one normalized citation as a single reference line."""
    c = normalize_citation(citation)
    location = f", p. {c['page']}" if c.get("page") is not None else ""
    return f"[{index}] {c['source']}{location} — {c['text']}" if c["text"] else f"[{index}] {c['source']}{location}"
