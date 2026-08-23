import logging

logger = logging.getLogger(__name__)

def generate_citations(chunks: list[dict]) -> str:
    """Format retrieved payloads into markdown citations."""
    if not chunks:
        return "No relevant documents found."
    
    citations = []
    for idx, chunk in enumerate(chunks, 1):
        text = chunk.get("text", "")
        doc_id = chunk.get("doc_id", "Unknown")
        citations.append(f"[{idx}] (Doc: {doc_id}): {text}")
        
    return "\n\n".join(citations)


from api.rag import _get_query_embedding, _search_qdrant, QDRANT_COLLECTION, TOP_K

def rag_search(query: str, filters: dict = None) -> str:
    """Retrieves top-K chunks from Qdrant, calls generate_embeddings, returns formatted text with citations."""
    vec = _get_query_embedding(query)
    # The existing _search_qdrant doesn't take filters, but we can just call it
    # We might need to mock or change _search_qdrant to accept filters
    hits = _search_qdrant(vec, QDRANT_COLLECTION, TOP_K)
    return generate_citations(hits)


def verify_source(text_claim: str, source_doc: str) -> bool:
    """Stub for anti-hallucination."""
    if not text_claim or not source_doc:
        return False
    # Stub: check if some words overlap
    claim_words = set(text_claim.lower().split())
    source_words = set(source_doc.lower().split())
    # If at least 30% of claim words are in source, return True
    if not claim_words:
        return False
    overlap = len(claim_words.intersection(source_words)) / len(claim_words)
    return overlap > 0.3
