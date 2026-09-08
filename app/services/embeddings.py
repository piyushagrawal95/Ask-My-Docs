import gc
from app.config import settings

_model = None

def _load_model():
    global _model
    if _model is None:
        from fastembed import TextEmbedding
        _model = TextEmbedding(model_name=settings.embedding_model)
    return _model

def embed_texts(texts: list[str]) -> list[list[float]]:
    if not texts:
        return []
    model = _load_model()
    vectors = list(model.embed(texts))
    result = [vec.tolist() for vec in vectors]
    del vectors
    gc.collect()
    return result

def embed_query(text: str) -> list[float]:
    return embed_texts([text])[0]

def rerank(query: str, candidates: list[str]) -> list[float]:
    # Reranker disabled permanently — free tier memory constraint.
    # Hybrid search (vector + BM25 + RRF) already provides good ranking.
    return [0.0] * len(candidates)