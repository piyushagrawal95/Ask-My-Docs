import time
import logging
import httpx
from app.config import settings

logger = logging.getLogger("embeddings")

_client = None
_MAX_BATCH = 100  # Voyage allows up to 128 texts per batch

def _get_client() -> httpx.Client:
    global _client
    if _client is None or _client.is_closed:
        _client = httpx.Client(timeout=45.0)
    return _client

def _get_headers() -> dict[str, str]:
    api_key = settings.voyage_api_key or settings.cohere_api_key
    return {
        "Authorization": f"Bearer {api_key}",
        "Content-Type": "application/json",
    }

def embed_texts(texts: list[str]) -> list[list[float]]:
    """Document ke chunks ko embed karta hai (jab document upload hota hai)."""
    if not texts:
        return []

    client = _get_client()
    headers = _get_headers()
    all_embeddings: list[list[float]] = []

    for i in range(0, len(texts), _MAX_BATCH):
        batch = texts[i : i + _MAX_BATCH]
        payload = {
            "input": batch,
            "model": settings.embedding_model,
            "input_type": "document",
        }

        for attempt in range(3):
            try:
                resp = client.post(
                    "https://api.voyageai.com/v1/embeddings",
                    headers=headers,
                    json=payload,
                )
                if resp.status_code == 429:
                    wait_time = 3 * (attempt + 1)
                    logger.warning(f"Voyage AI rate limit (429), retrying in {wait_time}s...")
                    time.sleep(wait_time)
                    continue

                resp.raise_for_status()
                data = resp.json()["data"]
                data.sort(key=lambda x: x["index"])
                batch_embeddings = [item["embedding"] for item in data]
                all_embeddings.extend(batch_embeddings)
                break
            except Exception as e:
                if attempt == 2:
                    raise RuntimeError(f"Voyage AI embedding failed after 3 attempts: {e}") from e
                time.sleep(2 * (attempt + 1))

    return all_embeddings

def embed_query(text: str) -> list[float]:
    """User ki search query ko embed karta hai."""
    client = _get_client()
    headers = _get_headers()
    payload = {
        "input": [text],
        "model": settings.embedding_model,
        "input_type": "query",
    }

    resp = client.post(
        "https://api.voyageai.com/v1/embeddings",
        headers=headers,
        json=payload,
    )
    resp.raise_for_status()
    return resp.json()["data"][0]["embedding"]

def rerank(query: str, candidates: list[str]) -> list[float]:
    """Voyage Cloud Reranker API call (rerank-2).
    Runs on Voyage's cloud infrastructure — 0 MB local RAM footprint.
    Re-scores candidate chunks against the user query for maximum precision."""
    if not candidates or not query:
        return [0.0] * len(candidates)

    client = _get_client()
    headers = _get_headers()
    payload = {
        "query": query,
        "documents": candidates,
        "model": settings.reranker_model,
        "top_k": len(candidates),
    }

    try:
        resp = client.post(
            "https://api.voyageai.com/v1/rerank",
            headers=headers,
            json=payload,
        )
        resp.raise_for_status()
        data = resp.json().get("data", [])
        scores = [0.0] * len(candidates)
        for item in data:
            scores[item["index"]] = float(item["relevance_score"])
        return scores
    except Exception as e:
        logger.warning(f"Reranker failed, falling back to hybrid scores: {e}")
        # Fail safe fallback: if Reranker call fails or rate-limits,
        # return 0.0 so candidate order from hybrid search RRF is preserved.
        return [0.0] * len(candidates)