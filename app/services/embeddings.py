import time
import cohere
from cohere.errors import TooManyRequestsError
from app.config import settings

_client = None
_MAX_BATCH = 96  # Cohere ek request mein max 96 texts allow karta hai

def _get_client():
    global _client
    if _client is None:
        _client = cohere.ClientV2(settings.cohere_api_key, timeout=30)
    return _client

def embed_texts(texts: list[str]) -> list[list[float]]:
    """Document ke chunks ko embed karta hai (jab document upload hota hai)."""
    if not texts:
        return []
    client = _get_client()
    all_embeddings: list[list[float]] = []
    for i in range(0, len(texts), _MAX_BATCH):
        batch = texts[i:i + _MAX_BATCH]
        for attempt in range(3):
            try:
                resp = client.embed(
                    texts=batch,
                    model=settings.embedding_model,
                    input_type="search_document",
                    embedding_types=["float"],
                )
                break
            except TooManyRequestsError:
                if attempt == 2:
                    raise
                time.sleep(5 * (attempt + 1))  # 5s, then 10s wait, phir retry
        all_embeddings.extend(resp.embeddings.float_)
        if i + _MAX_BATCH < len(texts):
            time.sleep(2)  # agla batch bhejne se pehle chhota delay
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