"""
POST /api/rag/search — Phase 3 M3 standalone RAG retrieval endpoint.

Accepts a query text, searches Qdrant, and returns the most relevant chunks.
This endpoint is independent of the agent loop so it can be tested standalone
and will later become a registered "tool" callable by the executor.
"""
import os
import logging
from fastapi import APIRouter, Depends
from pydantic import BaseModel
import httpx

from security.rbac import require_any_role
from api.auth import UserInfo

logger = logging.getLogger(__name__)
router = APIRouter()

OLLAMA_BASE_URL = os.getenv("OLLAMA_BASE_URL", "http://localhost:11434")
OLLAMA_EMBED_MODEL = os.getenv("OLLAMA_EMBED_MODEL", "nomic-embed-text")
QDRANT_URL = os.getenv("QDRANT_URL", None)
QDRANT_COLLECTION = os.getenv("QDRANT_COLLECTION", "kavach_docs")
TOP_K = int(os.getenv("RAG_TOP_K", "5"))


class RAGSearchRequest(BaseModel):
    query: str
    top_k: int = TOP_K
    collection: str = QDRANT_COLLECTION


class RAGSearchResult(BaseModel):
    chunk_index: int | None = None
    text: str
    score: float


class RAGSearchResponse(BaseModel):
    query: str
    results: list[RAGSearchResult]
    status: str


def _get_query_embedding(query: str) -> list[float]:
    """Generate a query embedding via Ollama. Falls back to zero vector on failure."""
    try:
        from models.registry import registry
        return registry.execute_embedding(OLLAMA_EMBED_MODEL, query)
    except Exception as exc:
        logger.warning("Embedding generation failed: %s — using zero vector fallback", exc)
        return [0.0] * 768


def _search_qdrant(query_vector: list[float], collection: str, top_k: int) -> list[dict]:
    """Search Qdrant for nearest neighbours. Returns list of {text, score, chunk_index}."""
    try:
        from qdrant_client import QdrantClient

        if QDRANT_URL:
            client = QdrantClient(url=QDRANT_URL)
        else:
            # In-memory fallback — no results if nothing was ingested this session
            client = QdrantClient(location=":memory:")

        hits = client.search(
            collection_name=collection,
            query_vector=query_vector,
            limit=top_k,
        )
        return [
            {
                "text": hit.payload.get("text", ""),
                "score": hit.score,
                "chunk_index": hit.payload.get("chunk_index"),
                "doc_id": hit.payload.get("doc_id"),
                "classification": hit.payload.get("classification", "internal"),
            }
            for hit in hits
        ]
    except Exception as exc:
        logger.warning("Qdrant search failed: %s", exc)
        return []


# Phase 9 (M3): a role may only retrieve chunks up to this classification tier.
_ROLE_MAX_CLASSIFICATION = {
    "viewer": ("public", "internal"),
    "operator": ("public", "internal", "confidential"),
    "admin": ("public", "internal", "confidential", "restricted"),
}


def filter_by_classification(chunks: list[dict], role: str) -> list[dict]:
    """Drop any chunk whose classification tier exceeds what `role` may see."""
    allowed = _ROLE_MAX_CLASSIFICATION.get(role, ("public", "internal"))
    return [c for c in chunks if c.get("classification", "internal") in allowed]


@router.post("/rag/search", response_model=RAGSearchResponse)
def rag_search(req: RAGSearchRequest, current_user: UserInfo = Depends(require_any_role)):
    """
    Phase 3 standalone RAG search endpoint.
    Embed the query → search Qdrant → filter by data classification (Phase 9)
    → return ranked chunks.
    """
    query_vector = _get_query_embedding(req.query)
    hits = _search_qdrant(query_vector, req.collection, req.top_k)
    hits = filter_by_classification(hits, current_user.role)

    results = [
        RAGSearchResult(
            text=h["text"],
            score=h["score"],
            chunk_index=h.get("chunk_index"),
        )
        for h in hits
    ]

    return RAGSearchResponse(
        query=req.query,
        results=results,
        status="ok",
    )
