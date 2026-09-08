import os
os.environ.setdefault("OMP_NUM_THREADS", "1")
os.environ.setdefault("TOKENIZERS_PARALLELISM", "false")

import gc
from app.config import settings

_model = None

def _load_model():
    global _model
    if _model is None:
        from sentence_transformers import SentenceTransformer
        import torch
        torch.set_num_threads(1)
        _model = SentenceTransformer(settings.embedding_model, device="cpu")
    return _model

def _unload_model():
    global _model
    _model = None
    gc.collect()

def embed_texts(texts: list[str]) -> list[list[float]]:
    model = _load_model()
    vectors = model.encode(
        texts,
        normalize_embeddings=True,
        show_progress_bar=False,
        batch_size=4,
    )
    result = vectors.tolist()
    del vectors
    _unload_model()
    return result

def embed_query(text: str) -> list[float]:
    return embed_texts([text])[0]

def rerank(query: str, candidates: list[str]) -> list[float]:
    # Temporarily disabled to save memory on free tier.
    return [0.0] * len(candidates)