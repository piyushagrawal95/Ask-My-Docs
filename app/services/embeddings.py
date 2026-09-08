import gc
from functools import lru_cache
from sentence_transformers import SentenceTransformer, CrossEncoder
from app.config import settings

EMBED_BATCH_SIZE = 16  # keep memory footprint small on low-RAM hosts

@lru_cache(maxsize=1)
def get_embedding_model() -> SentenceTransformer:
    return SentenceTransformer(settings.embedding_model)

@lru_cache(maxsize=1)
def get_reranker_model() -> CrossEncoder:
    return CrossEncoder(settings.reranker_model)

def embed_texts(texts:list[str]) -> list[list[float]]:
    model=get_embedding_model()
    all_vectors: list[list[float]] = []

    # Encode in small batches instead of one giant batch. This keeps peak
    # memory bounded regardless of how many chunks a document produces,
    # which matters a lot on low-RAM hosts (e.g. Render's free 512MB tier).
    for start in range(0, len(texts), EMBED_BATCH_SIZE):
        batch = texts[start:start + EMBED_BATCH_SIZE]
        vectors = model.encode(
            batch,
            normalize_embeddings=True,
            show_progress_bar=False,
            batch_size=EMBED_BATCH_SIZE,
        )
        all_vectors.extend(vectors.tolist())
        del vectors
        gc.collect()

    return all_vectors

def embed_query(text:str) -> list[float]:
    return embed_texts([text])[0]

def rerank(query:str,candidates:list[str]) -> list[float]:
    if not candidates:
        return []
    model=get_reranker_model()
    pairs=[[query,c] for c in candidates]
    scores=model.predict(pairs)
    return scores.tolist()