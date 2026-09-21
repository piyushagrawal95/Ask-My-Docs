from unittest.mock import patch, MagicMock
from app.services.retrieval import hybrid_search, RetrievedChunk

@patch("app.services.retrieval.bm25_search")
@patch("app.services.retrieval.vector_search")
def test_hybrid_search_ranks_chunk_found_by_both_retrievers_highest(mock_vector,mock_bm25):
    mock_vector.return_value=[
        RetrievedChunk(id="c1", document_id="d1", content="revenue grew",chunk_index=0, page_number=1, score=0.9),
        RetrievedChunk(id="c2",document_id="d1",content="unrelated text", chunk_index=1,page_number=2,score=0.5),
    ]

    mock_bm25.return_value=[
        RetrievedChunk(id="c1", document_id="d1", content="revenue grew",chunk_index=0, page_number=1, score=5.0),
        RetrievedChunk(id="c3", document_id="d1", content="other keyword hit", chunk_index=2, page_number=3, score=2.0)
    ]

    results=hybrid_search(["d1"],"revenue growth",query_embedding=[0.1]*384)

    assert results[0].id=="c1"
    assert len(results)==3


@patch("app.services.embeddings._get_client")
def test_rerank_calls_voyage_and_returns_scores(mock_get_client):
    from app.services.embeddings import rerank
    mock_client = MagicMock()
    mock_resp = MagicMock()
    mock_resp.status_code = 200
    mock_resp.json.return_value = {
        "data": [
            {"index": 0, "relevance_score": 0.2},
            {"index": 1, "relevance_score": 0.95},
        ]
    }
    mock_client.post.return_value = mock_resp
    mock_get_client.return_value = mock_client

    scores = rerank("ceo query", ["candidate 1", "candidate 2"])
    assert scores == [0.2, 0.95]


@patch("app.services.retrieval.rerank")
def test_rerank_candidates_reorders_by_score(mock_rerank):
    from app.services.retrieval import rerank_candidates
    candidates = [
        RetrievedChunk(id="c1", document_id="d1", content="low match", chunk_index=0, page_number=1, score=0.5),
        RetrievedChunk(id="c2", document_id="d1", content="high match", chunk_index=1, page_number=1, score=0.4),
    ]
    mock_rerank.return_value = [0.1, 0.9]

    results = rerank_candidates("query", candidates, top_k=2)
    assert results[0].id == "c2"
    assert results[0].score == 0.9
    assert results[1].id == "c1"
    assert results[1].score == 0.1


