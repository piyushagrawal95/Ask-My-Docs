import time
import logging
import cohere
from cohere.errors import TooManyRequestsError
from app.config import settings

logger = logging.getLogger("embeddings")

_client = None
_MAX_BATCH = 96  # Cohere allows up to 96 texts in a single request

def _get_client():
    global _client
    if _client is None:
        _client = cohere.ClientV2(settings.cohere_api_key, timeout=30)
    return _client

def embed_texts(texts: list[str]) -> list[list[float]]:
    """Document ke chunks ko embed karta hai (jab document upload hota hai).
    Smart rate-limiter: 6.5s delay between batches ensures we stay strictly
    under Cohere's 10 requests per minute free tier limit.
    """
    if not texts:
        return []

    client = _get_client()
    all_embeddings: list[list[float]] = []

    for i in range(0, len(texts), _MAX_BATCH):
        batch = texts[i : i + _MAX_BATCH]
        for attempt in range(4):
            try:
                resp = client.embed(
                    texts=batch,
                    model=settings.embedding_model,
                    input_type="search_document",
                    embedding_types=["float"],
                )
                all_embeddings.extend(resp.embeddings.float_)
                break
            except TooManyRequestsError:
                if attempt == 3:
                    raise
                wait_time = 15 * (attempt + 1)
                logger.warning(f"Cohere 429 rate limit hit, cooling down for {wait_time}s...")
                time.sleep(wait_time)
            except Exception as e:
                if attempt == 3:
                    raise
                time.sleep(5 * (attempt + 1))

        # Safe gap to guarantee < 10 RPM
        if i + _MAX_BATCH < len(texts):
            time.sleep(6.5)

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
    """Cohere Cloud Reranker API call.
    Runs on Cohere's cloud infrastructure — 0 MB local RAM footprint.
    Re-scores candidate chunks against the user query for maximum precision."""
    if not candidates or not query:
        return [0.0] * len(candidates)
    try:
        client = _get_client()
        resp = client.rerank(
            model=settings.reranker_model,
            query=query,
            documents=candidates,
        )
        scores = [0.0] * len(candidates)
        for item in resp.results:
            scores[item.index] = float(item.relevance_score)
        return scores
    except Exception as e:
        logger.warning(f"Reranker failed, falling back to hybrid scores: {e}")
        # Fail safe fallback: if Cohere call fails or rate-limits,
        # return 0.0 so candidate order from hybrid search RRF is preserved.
        return [0.0] * len(candidates)