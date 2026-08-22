"""
RAG Ingestion — Phase 1 implementation (M3).

chunk_document() splits plain text into overlapping fixed-size chunks
using sentence-boundary detection. This is the first step of the RAG
pipeline; embedding + Qdrant storage is added in Phase 2.
"""
from __future__ import annotations
import re


def chunk_document(
    document_text: str,
    chunk_size: int = 512,
    chunk_overlap: int = 64,
) -> list[dict]:
    """
    Split document_text into overlapping chunks for embedding.

    Args:
        document_text: Raw text extracted from a document.
        chunk_size:    Maximum characters per chunk.
        chunk_overlap: Characters of overlap between consecutive chunks.

    Returns:
        List of dicts: [{"chunk_index": int, "text": str, "char_start": int, "char_end": int}]

    Phase 2 will add metadata (doc_id, page, section heading) and call
    generate_embeddings() + store_chunks() to push into Qdrant.
    """
    if not document_text or not document_text.strip():
        return []

    # Normalise line endings and collapse whitespace runs
    text = re.sub(r"\r\n|\r", "\n", document_text)
    text = re.sub(r" {2,}", " ", text)

    # Split on sentence boundaries (period/exclamation/question + whitespace)
    sentence_pattern = re.compile(r"(?<=[.!?])\s+")
    sentences = sentence_pattern.split(text)

    chunks: list[dict] = []
    current_chunk: list[str] = []
    current_len = 0
    chunk_index = 0
    char_cursor = 0

    for sentence in sentences:
        sentence_len = len(sentence)

        # If adding this sentence would exceed the chunk size, flush the current chunk
        if current_len + sentence_len > chunk_size and current_chunk:
            chunk_text = " ".join(current_chunk)
            chunks.append(
                {
                    "chunk_index": chunk_index,
                    "text": chunk_text,
                    "char_start": char_cursor - current_len,
                    "char_end": char_cursor,
                }
            )
            chunk_index += 1

            # Keep the last `chunk_overlap` characters as context for the next chunk
            overlap_text = chunk_text[-chunk_overlap:] if chunk_overlap else ""
            current_chunk = [overlap_text] if overlap_text else []
            current_len = len(overlap_text)

        current_chunk.append(sentence)
        current_len += sentence_len + 1  # +1 for the space we'll join with
        char_cursor += sentence_len + 1

    # Flush remaining text
    if current_chunk:
        chunk_text = " ".join(current_chunk)
        chunks.append(
            {
                "chunk_index": chunk_index,
                "text": chunk_text,
                "char_start": max(0, char_cursor - current_len),
                "char_end": char_cursor,
            }
        )

    return chunks


import httpx
import os
import uuid

OLLAMA_BASE_URL = os.getenv("OLLAMA_BASE_URL", "http://localhost:11434")
OLLAMA_EMBED_MODEL = os.getenv("OLLAMA_EMBED_MODEL", "nomic-embed-text")

def generate_embeddings(chunks: list[dict]) -> list[dict]:
    """
    Phase 2 (M3): call the embedding model (nomic-embed-text via Ollama)
    and attach a 'vector' field to each chunk dict.
    """
    for chunk in chunks:
        payload = {
            "model": OLLAMA_EMBED_MODEL,
            "prompt": chunk["text"]
        }
        try:
            with httpx.Client() as client:
                resp = client.post(f"{OLLAMA_BASE_URL}/api/embeddings", json=payload)
                resp.raise_for_status()
                data = resp.json()
                chunk["vector"] = data.get("embedding", [])
        except Exception as e:
            # Fallback to mock embedding on failure
            chunk["vector"] = [0.0] * 768
            print(f"Warning: Failed to generate embedding via Ollama: {e}")
    return chunks


def store_chunks(chunks: list[dict], collection_name: str = "kavach_docs") -> None:
    """
    Phase 2 (M3): upsert chunk vectors + metadata into Qdrant.
    """
    try:
        from qdrant_client import QdrantClient
        from qdrant_client.models import Distance, VectorParams, PointStruct
    except ImportError:
        print("Warning: qdrant-client not installed, skipping storage.")
        return

    # In Dev, use memory storage if Qdrant is not running
    qdrant_url = os.getenv("QDRANT_URL")
    if qdrant_url:
        client = QdrantClient(url=qdrant_url)
    else:
        client = QdrantClient(location=":memory:")

    # Ensure collection exists
    try:
        client.get_collection(collection_name)
    except Exception:
        # Default vector size depends on the model; assume 768 for nomic-embed-text
        client.create_collection(
            collection_name=collection_name,
            vectors_config=VectorParams(size=768, distance=Distance.COSINE),
        )
    
    points = []
    for chunk in chunks:
        if "vector" not in chunk or not chunk["vector"]:
            continue
        
        point_id = str(uuid.uuid4())
        points.append(
            PointStruct(
                id=point_id,
                vector=chunk["vector"],
                payload={
                    "text": chunk["text"],
                    "chunk_index": chunk["chunk_index"]
                }
            )
        )
    
    if points:
        client.upsert(
            collection_name=collection_name,
            points=points
        )

