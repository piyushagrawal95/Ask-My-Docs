import gc
from app.config import settings

_model = None

EMBED_BATCH_SIZE = 16  # keep memory footprint small on low-RAM hosts

def _load_model():
    global _model
    if _model is None:
        from fastembed import TextEmbedding
        _model = TextEmbedding(model_name=settings.embedding_model)
    return _model

def embed_texts(texts: list[str]) -> list[list[float]]:
    model = _load_model()
    all_vectors: list[list[float]] = []

    # Process in small batches instead of materializing every embedding for
    # the whole document at once. Keeps peak memory bounded regardless of
    # how many chunks a document produces (important on low-RAM hosts).
    for start in range(0, len(texts), EMBED_BATCH_SIZE):
        batch = texts[start:start + EMBED_BATCH_SIZE]
        vectors = list(model.embed(batch, batch_size=EMBED_BATCH_SIZE))
        all_vectors.extend(vec.tolist() for vec in vectors)
        del vectors
        gc.collect()

    return all_vectors

def embed_query(text: str) -> list[float]:
    return embed_texts([text])[0]

def rerank(query: str, candidates: list[str]) -> list[float]:
    # Reranker disabled permanently — free tier memory constraint.
    # Hybrid search (vector + BM25 + RRF) already provides good ranking.
    return [0.0] * len(candidates)