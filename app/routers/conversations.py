from fastapi import APIRouter, Depends, HTTPException
from app.auth import get_current_user, CurrentUser
from app.database import get_service_client
from app.config import settings
from app.models.conversations import (
    AskQuestionRequest,
    ConversationDetailResponse,
    ConversationListResponse,
    ConversationResponse,
    MessageResponse,
    RenameConversationRequest
)
from app.services.retrieval import retrieve, RetrievalError, RetrievedChunk
from app.services.generation import generate_answer

router = APIRouter(prefix="/conversations", tags=["conversations"])

def make_title_from_question(question:str,max_length:int =50) ->str:
    """Derives a short conversation title from the first user question"""
    cleaned=question.strip().replace("\n"," ")
    if(len(cleaned)<=max_length):
        return cleaned
    return cleaned[:max_length]+ "..."




def _get_owned_conversation(client, conversation_id: str, user_id: str) -> dict:
    resp = (
        client.table("conversations")
        .select("*")
        .eq("id", conversation_id)
        .eq("owner_id", user_id)
        .execute()
    )
    if not resp.data:
        raise HTTPException(status_code=404, detail="Conversation not found.")
    return resp.data[0]


@router.post("", status_code=201, response_model=ConversationResponse)
async def create_conversation(user: CurrentUser = Depends(get_current_user)):
    client = get_service_client()
    resp = client.table("conversations").insert({"owner_id": user.id}).execute()
    return resp.data[0]


@router.get("", response_model=ConversationListResponse)
async def list_conversations(user: CurrentUser = Depends(get_current_user)):
    client = get_service_client()
    resp = (
        client.table("conversations")
        .select("*, documents(id)")
        .eq("owner_id", user.id)
        .order("updated_at", desc=True)
        .execute()
    )
    conversations = []
    for c in resp.data:
        docs = c.pop("documents", [])
        conversations.append({**c, "document_count": len(docs)})
    return {"conversations": conversations}


@router.get("/{conversation_id}", response_model=ConversationDetailResponse)
async def get_conversation(conversation_id: str, user: CurrentUser = Depends(get_current_user)):
    client = get_service_client()
    conversation = _get_owned_conversation(client, conversation_id, user.id)

    doc_count_resp = (
        client.table("documents")
        .select("id", count="exact")
        .eq("conversation_id", conversation_id)
        .execute()
    )

    messages_resp = (
        client.table("messages")
        .select("*, citations(*)")
        .eq("conversation_id", conversation_id)
        .order("created_at")
        .execute()
    )
    return {
        "conversation": {**conversation, "document_count": doc_count_resp.count or 0},
        "messages": messages_resp.data,
    }


@router.patch("/{conversation_id}", response_model=ConversationResponse)
async def rename_conversation(
    conversation_id: str,
    body: RenameConversationRequest,
    user: CurrentUser = Depends(get_current_user)
):
    client = get_service_client()
    _get_owned_conversation(client, conversation_id, user.id)

    # Cannot rename a chat with no documents uploaded
    doc_count_resp = (
        client.table("documents")
        .select("id", count="exact")
        .eq("conversation_id", conversation_id)
        .execute()
    )
    if (doc_count_resp.count or 0) == 0:
        raise HTTPException(
            status_code=400,
            detail="Cannot rename a chat with no documents uploaded."
        )

    title = body.title.strip()
    if not title:
        raise HTTPException(status_code=400, detail="Title cannot be empty.")
    title = title[:50]

    resp = client.table("conversations").update({"title": title}).eq("id", conversation_id).execute()
    return {**resp.data[0], "document_count": doc_count_resp.count or 0}

@router.delete("/{conversation_id}", status_code=204)
async def delete_conversation(conversation_id: str, user: CurrentUser = Depends(get_current_user)):
    client = get_service_client()
    _get_owned_conversation(client, conversation_id, user.id)  # 404s + ownership check

    # Clean up this conversation's uploaded files from storage first.
    # Deleting the conversation row cascades in the database (documents ->
    # document_chunks -> citations), but that only removes DB rows — the
    # actual files in the storage bucket need to be removed explicitly.
    docs_resp = (
        client.table("documents")
        .select("storage_path")
        .eq("conversation_id", conversation_id)
        .execute()
    )
    storage_paths = [d["storage_path"] for d in docs_resp.data]
    if storage_paths:
        try:
            client.storage.from_("documents").remove(storage_paths)
        except Exception:
            pass

    # Clean up messages (and their citations) first, in case the DB doesn't
    # have ON DELETE CASCADE set up on these foreign keys.
    messages_resp = (
        client.table("messages")
        .select("id")
        .eq("conversation_id", conversation_id)
        .execute()
    )
    message_ids = [m["id"] for m in messages_resp.data]
    if message_ids:
        client.table("citations").delete().in_("message_id", message_ids).execute()
        client.table("messages").delete().eq("conversation_id", conversation_id).execute()

    # Explicitly delete documents too (defensive, same reasoning as above).
    client.table("documents").delete().eq("conversation_id", conversation_id).execute()

    client.table("conversations").delete().eq("id", conversation_id).execute()
    return None


@router.post("/{conversation_id}/messages", status_code=201, response_model=MessageResponse)
async def ask_question(
    conversation_id: str,
    body: AskQuestionRequest,
    user: CurrentUser = Depends(get_current_user),
):
    client = get_service_client()
    _get_owned_conversation(client, conversation_id, user.id)  # 404s + ownership check

    # 1. Resolve which documents to search: only this conversation's ready documents
    docs_query=client.table("documents").select("id").eq("owner_id",user.id).eq("conversation_id",conversation_id).eq("status","ready")
    if body.document_id:
        docs_query=docs_query.eq("id",body.document_id)
    docs_resp=docs_query.execute()
    document_ids=[d["id"] for d in docs_resp.data]

    # 1b. Full document list (all statuses) for metadata queries (names, page count, etc.)
        # 1b. Full document list (all statuses) for metadata queries (names, page count, etc.)
    all_docs_resp=(client.table("documents").select("id,file_name,status,page_count").eq("owner_id",user.id).eq("conversation_id",conversation_id).execute())
    document_list = [
        {"file_name": d["file_name"], "status": d["status"], "page_count": d.get("page_count")}
        for d in all_docs_resp.data
    ]

    # If there are no documents in this conversation at all, skip the
    # retrieve/generate round-trip entirely and reply directly.
    if not all_docs_resp.data:
        client.table("messages").insert(
            {"conversation_id": conversation_id, "role": "user", "content": body.question}
        ).execute()
        assistant_row = (
            client.table("messages")
            .insert(
                {
                    "conversation_id": conversation_id,
                    "role": "assistant",
                    "content": "You don't have any processed documents yet to answer this from. Upload a document first.",
                    "is_answerable": False,
                }
            )
            .execute()
        ).data[0]
        return {**assistant_row, "citations": []}

    # Check if this is the first message of the conversation (for auto titling)
    existing_messages=(
        client.table("messages")
        .select("id").eq("conversation_id",conversation_id).limit(1).execute()
    )
    is_first_message=len(existing_messages.data)==0

    # Fetch recent conversation history (before saving the new message) so
    # follow-up requests like "explain that in Hindi" have context.
    history_resp = (
        client.table("messages")
        .select("role, content, citations(document_id)")
        .eq("conversation_id", conversation_id)
        .order("created_at", desc=True)
        .limit(30)
        .execute()
    )
    raw_history = list(reversed(history_resp.data))

    # Drop any assistant answer (and its preceding question) that was based
    # on a document which has since been deleted — otherwise the model can
    # still "recall" that fact straight from the visible history text, no
    # matter what the prompt says.
    existing_document_ids = {d["id"] for d in all_docs_resp.data}
    history = []
    for turn in raw_history:
        if turn["role"] == "assistant":
            citations=turn.get("citations") or []
            has_dangling_citation=any(c.get("document_id") is None for c in citations)
            cited_doc_ids={c["document_id"] for c in citations if c.get("document_id")}
            
            is_stale = has_dangling_citation or  (bool(cited_doc_ids) and not cited_doc_ids.issubset(existing_document_ids))
            if is_stale:
                if history and history[-1]["role"] == "user":
                    history.pop()
                continue
        history.append({"role": turn["role"], "content": turn["content"]})

    # 2. Save the user's message first
    client.table("messages").insert(
        {"conversation_id": conversation_id, "role": "user", "content": body.question}
    ).execute()

    # 3. Retrieve -> generate
    try:
        SUMMARIZE_ALL_TRIGGER = "please summarize all documents"
        if body.question.strip().lower().rstrip(".") == SUMMARIZE_ALL_TRIGGER and len(document_ids) > 1:
            # Fair per-document split: guarantee every document contributes
            # chunks, instead of letting global similarity crowd one out.
            per_doc_limit = max(2, settings.retrieval_top_k // len(document_ids))
            chunks = []
            for doc_id in document_ids:
                resp = (
                    client.table("document_chunks")
                    .select("id, document_id, content, chunk_index, page_number")
                    .eq("document_id", doc_id)
                    .order("chunk_index")
                    .limit(per_doc_limit)
                    .execute()
                )
                chunks.extend([
                    RetrievedChunk(
                        id=row["id"],
                        document_id=row["document_id"],
                        content=row["content"],
                        chunk_index=row["chunk_index"],
                        page_number=row.get("page_number"),
                        score=1.0,
                    )
                    for row in resp.data
                ])
        else:
            chunks = retrieve(document_ids, body.question)
        result = generate_answer(body.question, chunks, history,document_list)
    except RetrievalError:
        assistant_row = (
            client.table("messages")
            .insert(
                {
                    "conversation_id": conversation_id,
                    "role": "assistant",
                    "content": "Something went wrong while searching your documents. Please try asking again in a moment.",
                    "is_answerable": False,
                }
            )
            .execute()
        ).data[0]
        return {**assistant_row, "citations": []}

    # 4. Save assistant message
    assistant_row = (
        client.table("messages")
        .insert(
            {
                "conversation_id": conversation_id,
                "role": "assistant",
                "content": result.answer,
                "is_answerable": result.is_answerable,
            }
        )
        .execute()
    ).data[0]

    # 5. Save citations, linked to the assistant message
    saved_citations = []
    if result.citations:
        citation_rows = [
            {
                "message_id": assistant_row["id"],
                "document_id": c.document_id,
                "chunk_id": c.chunk_id,
                "page_number": c.page_number,
                "snippet": c.snippet,
            }
            for c in result.citations
        ]
        citations_resp = client.table("citations").insert(citation_rows).execute()
        saved_citations = citations_resp.data

        # 6. Auto-title the conversation from the first question
    if is_first_message:
        title = make_title_from_question(body.question)
        client.table("conversations").update({"title": title}).eq(
            "id", conversation_id
        ).execute()

    return {**assistant_row, "citations": saved_citations}