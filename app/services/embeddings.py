import gc
from app.config import settings

_model = None
_reranker = None

def _load_model():
    global _model
    if _model is None:
        from fastembed import TextEmbedding
        _model = TextEmbedding(model_name=settings.embedding_model)
    return _model

def _load_reranker():
    global _reranker
    if _reranker is None:
        from fastembed.rerank.cross_encoder import TextCrossEncoder
        _reranker = TextCrossEncoder(model_name=settings.reranker_model)
    return _reranker

def _unload_reranker():
    global _reranker
    _reranker = None
    gc.collect()

def embed_texts(texts: list[str]) -> list[list[float]]:
    model = _load_model()
    embeddings = list(model.embed(texts))
    return [vec.tolist() for vec in embeddings]

def embed_query(text: str) -> list[float]:
    return embed_texts([text])[0]

def rerank(query: str, candidates: list[str]) -> list[float]:
    if not candidates:
        return []
    model = _load_reranker()
    scores = list(model.rerank(query, candidates))
    _unload_reranker()
    return [float(s) for s in scores]