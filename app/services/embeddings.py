import os
os.environ.setdefault("OMP_NUM_THREADS", "1")
os.environ.setdefault("TOKENIZERS_PARALLELISM", "false")

import gc
from functools import lru_cache
from app.config import settings

@lru_cache(maxsize=1)
def get_embedding_model():
    from sentence_transformers import SentenceTransformer
    import torch
    torch.set_num_threads(1)
    return SentenceTransformer(settings.embedding_model, device="cpu")

@lru_cache(maxsize=1)
def get_reranker_model():
    from sentence_transformers import CrossEncoder
    import torch
    torch.set_num_threads(1)
    return CrossEncoder(settings.reranker_model, device="cpu")

def embed_texts(texts: list[str]) -> list[list[float]]:
    model = get_embedding_model()
    vectors = model.encode(
        texts,
        normalize_embeddings=True,
        show_progress_bar=False,
        batch_size=8,
    )
    result = vectors.tolist()
    del vectors
    gc.collect()
    return result

def embed_query(text: str) -> list[float]:
    return embed_texts([text])[0]

def rerank(query: str, candidates: list[str]) -> list[float]:
    if not candidates:
        return []
    model = get_reranker_model()
    pairs = [[query, c] for c in candidates]
    scores = model.predict(pairs, batch_size=8)
    result = scores.tolist()
    del scores
    gc.collect()
    return result