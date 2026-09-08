from dataclasses import dataclass
from app.database import get_service_client
from app.services.embeddings import embed_query,rerank
from app.config import settings

CANDIDATE_POOL_SIZE=settings.candidate_pool_size
RRF_K=settings.rrf_k

@dataclass
class RetrievedChunk:
    id:str
    document_id:str
    content:str
    chunk_index:int
    page_number:int|None
    score:float

def vector_search(document_ids:list[str],query_embedding:list[float],k:int = CANDIDATE_POOL_SIZE) ->list[RetrievedChunk]:
    client=get_service_client()
    resp=client.rpc(
        "match_document_chunks",{
            "p_document_ids":document_ids,
            "p_query_embedding":query_embedding,
            "p_match_count":k
        }
    ).execute()

    return[
        RetrievedChunk(
            id=row["id"],
            document_id=row["document_id"],
            content=row["content"],
            chunk_index=row["chunk_index"],
            page_number=row.get("page_number"),
            score=row["similarity"],
        )
        for row in resp.data
    ]


def bm25_search(document_ids:list[str],query:str,k:int=CANDIDATE_POOL_SIZE) -> list[RetrievedChunk]:
    client=get_service_client()
    resp=client.rpc(
        "search_document_chunks_bm25",{
            "p_document_ids":document_ids,
            "p_query":query,
            "p_match_count":k
        }
    ).execute()

    return[
        RetrievedChunk(
            id=row["id"],
            document_id=row["document_id"],
            content=row["content"],
            chunk_index=row["chunk_index"],
            page_number=row.get("page_number"),
            score=row["rank"],
        )
        for row in resp.data
    ]


def hybrid_search(document_id:list[str],query:str,query_embedding:list[float],k:int=CANDIDATE_POOL_SIZE) -> list[RetrievedChunk]:
    vector_results=vector_search(document_id,query_embedding,k)
    keyword_results=bm25_search(document_id,query,k)
    fused_scores:dict[str,float]={}
    chunk_lookup:dict[str,RetrievedChunk]={}

    for rank_position, chunk in enumerate(vector_results):
        fused_scores[chunk.id]=fused_scores.get(chunk.id,0.0)+1.0/(RRF_K+rank_position+1)
        chunk_lookup[chunk.id]=chunk

    for rank_position,chunk in enumerate(keyword_results):
        fused_scores[chunk.id]=fused_scores.get(chunk.id,0.0)+1.0/(RRF_K+rank_position+1)
        chunk_lookup.setdefault(chunk.id,chunk)

    fused=[
        RetrievedChunk(
            id=chunk_lookup[chunk_id].id,
            document_id=chunk_lookup[chunk_id].document_id,
            content=chunk_lookup[chunk_id].content,
            chunk_index=chunk_lookup[chunk_id].chunk_index,
            page_number=chunk_lookup[chunk_id].page_number,
            score=score,
        )
        for chunk_id,score in fused_scores.items()
    ]
    fused.sort(key=lambda c:c.score,reverse=True)
    return fused


def rerank_candidates(query:str, candidates:list[RetrievedChunk],top_k:int) -> list[RetrievedChunk]:
    if not candidates:
        return []

    scores=rerank(query,[c.content for c in candidates])
    reranked=[
        RetrievedChunk(
            id=c.id,
            document_id=c.document_id,
            content=c.content,
            chunk_index=c.chunk_index,
            page_number=c.page_number,
            score=float(score)
        )
        for c,score in zip(candidates,scores)
    ]
    reranked.sort(key=lambda c:c.score,reverse=True)
    return reranked[:top_k]


def retrieve(document_ids:list[str],query:str,top_k:int=None):
    if not document_ids:
        return []

    top_k=top_k if top_k is not None else settings.retrieval_top_k
    query_embedding=embed_query(query)
    candidates=hybrid_search(document_ids,query,query_embedding,k=CANDIDATE_POOL_SIZE)
    return rerank_candidates(query,candidates,top_k=top_k)


