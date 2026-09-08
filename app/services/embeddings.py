from functools import lru_cache
from app.config import settings

@lru_cache(maxsize=1)
def get_embedding_model():
    from sentence_transformers import SentenceTransformer
    return SentenceTransformer(settings.embedding_model)

@lru_cache(maxsize=1)
def get_reranker_model():
    from sentence_transformers import CrossEncoder
    return CrossEncoder(settings.reranker_model)

def embed_texts(texts: list[str]) -> list[list[float]]:
    model = get_embedding_model()
    vectors = model.encode(texts, normalize_embeddings=True, show_progress_bar=False)
    return vectors.tolist()

def embed_query(text: str) -> list[float]:
    return embed_texts([text])[0]

def rerank(query: str, candidates: list[str]) -> list[float]:
    if not candidates:
        return []
    model = get_reranker_model()
    pairs = [[query, c] for c in candidates]
    scores = model.predict(pairs)
    return scores.tolist()