import json
from unittest.mock import MagicMock,patch

from app.services.generation import generate_answer
from app.services.retrieval import RetrievedChunk

def _fake_groq_response(payload:dict):
    resp=MagicMock()
    resp.choices=[MagicMock(message=MagicMock(content=json.dumps(payload)))]
    return resp

def test_generate_answer_no_chunks_returns_not_answerable():
    result=generate_answer("What is the revenue",[])
    assert result.is_answerable is False
    assert result.citations==[]

@patch("app.services.generation.Groq")
def test_generate_answer_maps_citations_correctly(mock_groq_cls):
    chunks=[
        RetrievedChunk(id="chunk-1",document_id="doc-1",content="Revenue grew 12%", chunk_index=0,page_number=3, score=0.9)
    ]
    mock_client=MagicMock()
    mock_client.chat.completions.create.return_value=_fake_groq_response({"answer":"Revenue grew 12% [1].","is_answerable":True,"cited_excerpts":[1]})
    mock_groq_cls.return_value=mock_client

    result=generate_answer("How much did revenue grow",chunks)

    assert result.is_answerable is True
    assert len(result.citations)==1
    assert result.citations[0].chunk_id=="chunk-1"
    assert result.citations[0].page_number==3


@patch("app.services.generation.Groq")
def test_generate_answer_handles_invalid_json_gracefully(mock_groq_cls):
    chunks=[RetrievedChunk(id="chunk-1",document_id="doc-1",content="text",chunk_index=0,page_number=1,score=0.9)]
    mock_client=MagicMock()
    resp=MagicMock()
    resp.choices=[MagicMock(message=MagicMock(content="not valid json"))]
    mock_client.chat.completions.create.return_value=resp
    mock_groq_cls.return_value=mock_client

    result=generate_answer("question",chunks)
    assert result.is_answerable is False