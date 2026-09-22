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


@patch("app.services.generation.Groq")
def test_generate_answer_strips_various_citation_markers(mock_groq_cls):
    chunks = [
        RetrievedChunk(id="chunk-1", document_id="doc-1", content="Text", chunk_index=0, page_number=1, score=0.9),
        RetrievedChunk(id="chunk-2", document_id="doc-1", content="Text 2", chunk_index=1, page_number=1, score=0.8),
    ]
    mock_client = MagicMock()
    mock_client.chat.completions.create.return_value = _fake_groq_response({
        "answer": "Meera is CEO [excerpt 1]. Founded in 2016 [excerpts 1, 2] in Pune (excerpt 1).",
        "is_answerable": True,
        "cited_excerpts": [1, 2]
    })
    mock_groq_cls.return_value = mock_client

    result = generate_answer("Who is CEO", chunks)
    assert result.is_answerable is True
    assert "[excerpt" not in result.answer.lower()
    assert "(excerpt" not in result.answer.lower()
    assert result.answer == "Meera is CEO. Founded in 2016 in Pune."


@patch("app.services.generation.Groq")
def test_generate_answer_includes_document_names_in_prompt(mock_groq_cls):
    chunks = [
        RetrievedChunk(id="chunk-1", document_id="doc-1", content="Resume of Alice", chunk_index=0, page_number=1, score=0.9),
        RetrievedChunk(id="chunk-2", document_id="doc-2", content="Job Description for Senior Dev", chunk_index=0, page_number=2, score=0.85),
    ]
    doc_name_map = {"doc-1": "Alice_Resume.pdf", "doc-2": "Job_Spec.docx"}
    mock_client = MagicMock()
    mock_client.chat.completions.create.return_value = _fake_groq_response({
        "answer": "Alice_Resume is an applicant CV while Job_Spec is an open vacancy description.",
        "is_answerable": True,
        "cited_excerpts": [1, 2]
    })
    mock_groq_cls.return_value = mock_client

    result = generate_answer(
        "how these doc differ from each other",
        chunks,
        doc_name_map=doc_name_map
    )

    assert result.is_answerable is True
    call_args = mock_client.chat.completions.create.call_args
    user_prompt = call_args[1]["messages"][-1]["content"]
    assert "Document: Alice_Resume.pdf" in user_prompt
    assert "Document: Job_Spec.docx" in user_prompt
