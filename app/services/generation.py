import json
from dataclasses import dataclass
from groq import Groq
from app.config import settings
from app.services.retrieval import RetrievedChunk

LLM_MODEL = settings.llm_model

SYSTEM_PROMPT="""You are a careful assistant that answers questions using ONLY the numbered context excerpts provided by the user, using the recent conversation history (if given) to understand follow-up requests.

Rules:
1. Only use information present in the context excerpts below. Never use outside knowledge.
2. Every factual claim in your answer must be traceable to one or more excerpts.Reference them by number e.g. "Revenue grew 12%[2]."
3. If the excerpts do not contain enough information to answer the question, set "is_answerable" to false and explain briefly what's missing- do not guess or fabricate answer.
4. If the user's current message is a follow-up about the conversation itself rather than a new question about the documents — for example "explain that in Hindi", "translate the last answer", "summarize that shorter", "isko hindi mein samjhao" — use the conversation history to figure out what it refers to, and fulfill the request (translate/rephrase/shorten the earlier assistant answer). Treat this as answerable (is_answerable: true) even if the excerpts alone wouldn't answer it, since you're reusing information already given earlier in the conversation. Keep the original citation numbers where they still apply.
5. Match the language and script of the user's CURRENT message: if they write in Hindi (Devanagari script), answer fully in Hindi. If they write in Hinglish (Hindi words typed in Roman/English letters), answer in Hinglish the same way. If they write in English, answer in English. Never switch script/language on your own.
6. Format the "answer" text using Markdown for readability: use short paragraphs, "- " for bullet lists when listing multiple items, and "**bold**" for key terms or numbers. Do not use headings (#).
7. Respond with ONLY a JSON object, no other text , in this exact shape:
{"answer":"<markdown-formatted answer text with [n] citation markers inline>","is_answerable":true/false,"cited_excerpts":[<excerpt numbers you actually used>]}
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

def generate_answer(query:str,chunks:list[RetrievedChunk],history:list[dict]|None=None) -> GeneratedAnswer:
    history = history or []

    if not chunks and not history:
        return GeneratedAnswer(
            answer="I couldn't find any relevant information in your documents to answer this question",
            is_answerable=False,
            citations=[]
        )

    context_block=(
        _build_context_block(chunks)
        if chunks
        else "(No new excerpts were retrieved for this message — rely on the conversation history below.)"
    )
    client=Groq(api_key=settings.groq_api_key)

    messages=[{"role":"system","content":SYSTEM_PROMPT}]
    for turn in history:
        messages.append({"role":turn["role"],"content":turn["content"]})
    messages.append({"role":"user","content":f"Context excerpts:\n\n{context_block}\n\nQuestion:{query}"})

    try:
        response=client.chat.completions.create(
            model=LLM_MODEL,
            response_format={"type":"json_object"},
            temperature=0,
            messages=messages
        )
    except Exception:
        # Groq down/rate-limited/timeout — fail safe instead of a raw 500.
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