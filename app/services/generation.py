import json
import logging
from dataclasses import dataclass
from groq import Groq
from app.config import settings
from app.services.retrieval import RetrievedChunk
from app.prompts import SYSTEM_PROMPT

LLM_MODEL = settings.llm_model

@dataclass
class Citation:
    chunk_id:str
    document_id:str
    page_number:int|None
    snippet:str

@dataclass
class GeneratedAnswer:
    answer:str
    is_answerable:bool
    citations:list[Citation]


def _build_context_block(chunks:list[RetrievedChunk], doc_name_map: dict[str, str] | None = None)->str:
    doc_name_map = doc_name_map or {}
    parts=[]
    for i, chunk in enumerate(chunks,start=1):
        doc_name = doc_name_map.get(chunk.document_id) or chunk.file_name or ""
        doc_info = f"Document: {doc_name}" if doc_name else ""
        page_info = f"page {chunk.page_number}" if chunk.page_number else ""
        labels = ", ".join(filter(None, [doc_info, page_info]))
        header = f"({labels})" if labels else ""
        parts.append(f"[{i}]{header}: {chunk.content}")
    return "\n\n".join(parts)


def _build_document_list_block(document_list:list[dict]|None)->str:
    if not document_list:
        return "(No documents uploaded in this conversation yet.)"
    lines=[]
    for d in document_list:
        pages_str = f", total pages: {d['page_count']}" if d.get('page_count') is not None else ""
        lines.append(f"- {d['file_name']} (status: {d['status']}{pages_str})")
    return "Uploaded documents in this conversation:\n" + "\n".join(lines)


def generate_answer(
    query:str,
    chunks:list[RetrievedChunk],
    history:list[dict]|None=None,
    document_list:list[dict]|None=None,
    doc_name_map:dict[str,str]|None=None
) -> GeneratedAnswer:
    history = history or []

    if not chunks and not history and not document_list:
        return GeneratedAnswer(
            answer="I couldn't find any relevant information in your documents to answer this question",
            is_answerable=False,
            citations=[]
        )

    context_block=(
        _build_context_block(chunks, doc_name_map)
        if chunks
        else "(No new excerpts were retrieved for this message — rely on the conversation history and document list below.)"
    )
    document_list_block=_build_document_list_block(document_list)
    client=Groq(api_key=settings.groq_api_key)

    messages=[{"role":"system","content":SYSTEM_PROMPT}]
    for turn in history:
        messages.append({"role":turn["role"],"content":turn["content"]})
    messages.append({"role":"user","content":f"{document_list_block}\n\nContext excerpts:\n\n{context_block}\n\nQuestion:{query}"})

    try:
        response=client.chat.completions.create(
            model=LLM_MODEL,
            response_format={"type":"json_object"},
            temperature=0,
            messages=messages
        )
    except Exception as e:
        # Groq down/rate-limited/timeout — fail safe instead of a raw 500.
        logging.error(f"Groq call failed:{e!r}")
        return GeneratedAnswer(
            answer="The AI service is temporarily unavailable. Please try asking again in a moment.",
            is_answerable=False,
            citations=[]
        )

    raw=response.choices[0].message.content
    try:
        parsed=json.loads(raw)
    except json.JSONDecodeError:
        #LLM didn't return valid JSON, fail safe instead of guessing
        return GeneratedAnswer(
            answer="Something went wrong generating an answer from your documents.Please try again",
            is_answerable=False,
            citations=[]
        )
    raw_answer = parsed.get("answer", "")
    import re
    # Clean up bracketed citation markers e.g. [1], [1, 2], [excerpt 1], [Excerpts 1, 2], [source 1]
    cleaned = re.sub(
        r"\[\s*(?:(?:excerpt|excerpts|source|sources|doc|docs|document|page|pages|ref|reference)s?\s*:?)?\s*#?\d+(?:\s*(?:,|and|&|–|-)\s*#?\d+)*\s*\]",
        "",
        raw_answer,
        flags=re.IGNORECASE,
    )
    # Clean up parenthesized citation markers e.g. (excerpt 1), (excerpts 1, 2)
    cleaned = re.sub(
        r"\(\s*(?:excerpt|excerpts|source|sources|doc|docs|document|page|pages|ref|reference)s?\s*:?\s*#?\d+(?:\s*(?:,|and|&|–|-)\s*#?\d+)*\s*\)",
        "",
        cleaned,
        flags=re.IGNORECASE,
    )
    # Clean up any trailing/orphan citation markers e.g. [excerpt]
    cleaned = re.sub(
        r"\[\s*(?:excerpt|excerpts|source|sources|reference)s?\s*\]",
        "",
        cleaned,
        flags=re.IGNORECASE,
    )
    cleaned = re.sub(r"\s+([.,;:!?])", r"\1", cleaned)
    answer_text = re.sub(r"[ \t]+", " ", cleaned).strip()

    is_answerable=parsed.get("is_answerable",False)
    cited_numbers=parsed.get("cited_excerpts",[])

    citations=[]
    for n in cited_numbers:
        idx=n-1
        if 0<=idx<len(chunks):
            c=chunks[idx]
            citations.append(
                Citation(
                    chunk_id=c.id,
                    document_id=c.document_id,
                    page_number=c.page_number,
                    snippet=c.content[:300]
                )
            )

    return GeneratedAnswer(answer=answer_text,is_answerable=is_answerable,citations=citations)