from unittest.mock import patch
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


