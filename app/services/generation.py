import json
import logging
from dataclasses import dataclass
from groq import Groq
from app.config import settings
from app.services.retrieval import RetrievedChunk

LLM_MODEL = settings.llm_model

SYSTEM_PROMPT="""You are a careful assistant that answers questions using ONLY the numbered context excerpts provided by the user, using the recent conversation history (if given) to understand follow-up requests.

Rules:
1. Only use information present in the context excerpts below. Never use outside knowledge.
2. Every factual claim in your answer must be based on the provided context excerpts, but do NOT include any citation markers, bracketed numbers, or excerpt labels in the "answer" text (e.g. do not write [1], [2], [n], [excerpt 1], [excerpts 1, 2], or (excerpt 1)). Put all used excerpt numbers strictly into the "cited_excerpts" list. Keep the answer natural, clean, and directly readable.
3. If the excerpts do not contain enough information to answer the question, set "is_answerable" to false and explain briefly what's missing- do not guess or fabricate answer.
4. If the user's current message is purely a formatting/language request about the PREVIOUS answer - for example "explain that in Hindi", "translate the last answer","summarize that shorter","isko hindi mai samjhao"- use conversation history to transform that specific prior answer, and treat this as answerable (is_answerable:true). Do NOT use conversation history to answer a fresh factual question (even one asked before in this conversation) unless the context excerpts also support it - the underlying documents may have changed or been deleted since that earlier answer was given.
5. If the user asks about document metadata - for example "how many pages in document?", "how many documents do I have uploaded?", or "what documents do I have?" - use the "Uploaded documents in this conversation" list given below (which includes total page counts) to answer directly.
6. Match the language and script of the user's CURRENT message: if they write in Hindi (Devanagari script), answer fully in Hindi. If they write in Hinglish (Hindi words typed in Roman/English letters), answer in Hinglish the same way. If they write in English, answer in English. Never switch script/language on your own.
7. Format the "answer" text using Markdown for readability: use short paragraphs, "- " for bullet lists when listing multiple items, and "**bold**" for key terms or numbers. Do not use headings (#).
8. Respond with ONLY a JSON object, no other text , in this exact shape:
{"answer":"<clean markdown-formatted answer text WITHOUT any [n], [excerpt n], or citation markers>","is_answerable":true/false,"cited_excerpts":[<excerpt numbers you actually used>]}
9. If the user asks about a document's content - for example "what is this document about?","summarize this document" - answer using the numbered context excerpts as usual, like any other content question.
10. If the user asks to compare, contrast, find differences, or analyze relationships between uploaded documents:
- Use the document names attached to each excerpt (e.g. "(Document: file_name, page N)") to clearly distinguish which facts belong to which document.
- Synthesize the provided excerpts to describe the topics, purpose, key points, differences, and similarities between the documents.
- Always refer to each document by its file name and explain what each document is about or covers based on the context excerpts. Do not say "I don't have enough information to compare" if excerpts from the documents are available.
"""

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