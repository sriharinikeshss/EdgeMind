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


def generate_embeddings(chunks: list[dict]) -> list[dict]:
    """
    TODO Phase 2 (M3): call the embedding model (BGE-M3 via Ollama)
    and attach a 'vector' field to each chunk dict.
    """
    raise NotImplementedError("Embedding generation implemented in Phase 2.")


def store_chunks(chunks: list[dict], collection_name: str = "kavach_docs") -> None:
    """
    TODO Phase 2 (M3): upsert chunk vectors + metadata into Qdrant.
    """
    raise NotImplementedError("Qdrant chunk storage implemented in Phase 2.")

