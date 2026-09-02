import json
from dataclasses import dataclass
from groq import Groq
from app.config import settings
from app.services.retrieval import RetrievedChunk

LLM_MODEL = "openai/gpt-oss-120b"

SYSTEM_PROMPT="""You are a careful assistant that answers questions using ONLY the numbered context excerpts provided by the user

Rules:
1. Only use information present in the context excerpts below. Never use outside knowledge.
2. Every factual claim in your answer must be traceable to one or more excerpts.Reference them by number e.g. "Revenue grew 12%[2]."
3. If the excerpts do not contain enough information to answer the question, set "is_answerable" to false and explain briefly what's missing- do not guess or fabricate answer.
4. Respond with ONLY a JSON object, no other text , in this exact shape:
{"answer":"<answer text with [n] citation markers inline>","is_answerable":true/false,"cited_excerpts":[<excerpt numbers you actually used>]}
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


def _build_context_block(chunks:list[RetrievedChunk])->str:
    parts=[]
    for i, chunk in enumerate(chunks,start=1):
        page_info=f"(page{chunk.page_number})" if chunk.page_number else ""
        parts.append(f"[{i}]{page_info}:{chunk.content}")
    return "\n\n".join(parts)

def generate_answer(query:str,chunks:list[RetrievedChunk]) -> GeneratedAnswer:
    if not chunks:
        return GeneratedAnswer(
            answer="I couldn't find any relevant information in your documents to answer this question",
            is_answerable=False,
            citations=[]
        )

    context_block=_build_context_block(chunks)
    client=Groq(api_key=settings.groq_api_key)

    response=client.chat.completions.create(
        model=LLM_MODEL,
        response_format={"type":"json_object"},
        temperature=0,
        messages=[
            {"role":"system","content":SYSTEM_PROMPT},
            {"role":"user","content":f"Context excerpts:\n\n{context_block}\n\nQuestion:{query}"},

        ]
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
    answer_text=parsed.get("answer","")
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
