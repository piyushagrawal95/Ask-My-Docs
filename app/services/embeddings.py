import cohere
from app.config import settings

_client = None
_MAX_BATCH = 96  # Cohere ek request mein max 96 texts allow karta hai

def _get_client():
    global _client
    if _client is None:
        _client = cohere.ClientV2(settings.cohere_api_key)
    return _client

def embed_texts(texts: list[str]) -> list[list[float]]:
    """Document ke chunks ko embed karta hai (jab document upload hota hai)."""
    if not texts:
        return []
    client = _get_client()
    all_embeddings: list[list[float]] = []
    for i in range(0, len(texts), _MAX_BATCH):
        batch = texts[i:i + _MAX_BATCH]
        resp = client.embed(
            texts=batch,
            model=settings.embedding_model,
            input_type="search_document",
            embedding_types=["float"],
        )
        all_embeddings.extend(resp.embeddings.float_)
    return all_embeddings

def embed_query(text: str) -> list[float]:
    """User ki search query ko embed karta hai."""
    client = _get_client()
    resp = client.embed(
        texts=[text],
        model=settings.embedding_model,
        input_type="search_query",
        embedding_types=["float"],
    )
    return resp.embeddings.float_[0]

def rerank(query: str, candidates: list[str]) -> list[float]:
    # Reranker permanently disabled — 512MB memory constraint.
    return [0.0] * len(candidates)