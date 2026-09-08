from fastapi import APIRouter, Depends, HTTPException
from app.auth import get_current_user, CurrentUser
from app.database import get_service_client
from app.models.conversations import (
    AskQuestionRequest,
    ConversationDetailResponse,
    ConversationListResponse,
    ConversationResponse,
    MessageResponse,
)
from app.services.retrieval import retrieve
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
        .select("*")
        .eq("owner_id", user.id)
        .order("updated_at", desc=True)
        .execute()
    )
    return {"conversations": resp.data}


@router.get("/{conversation_id}", response_model=ConversationDetailResponse)
async def get_conversation(conversation_id: str, user: CurrentUser = Depends(get_current_user)):
    client = get_service_client()
    conversation = _get_owned_conversation(client, conversation_id, user.id)

    messages_resp = (
        client.table("messages")
        .select("*, citations(*)")
        .eq("conversation_id", conversation_id)
        .order("created_at")
        .execute()
    )
    return {"conversation": conversation, "messages": messages_resp.data}

@router.delete("/{conversation_id}", status_code=204)
async def delete_conversation(conversation_id: str, user: CurrentUser = Depends(get_current_user)):
    client = get_service_client()
    _get_owned_conversation(client, conversation_id, user.id)  # 404s + ownership check

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

    # 1. Resolve which documents to search: explicit list (ownership-checked) or all of the user's ready docs
    if body.document_ids:
        docs_resp = (
            client.table("documents")
            .select("id")
            .in_("id", body.document_ids)
            .eq("owner_id", user.id)
            .eq("status", "ready")
            .execute()
        )
    else:
        docs_resp = (
            client.table("documents")
            .select("id")
            .eq("owner_id", user.id)
            .eq("status", "ready")
            .execute()
        )
    document_ids = [d["id"] for d in docs_resp.data]

    # Check if this is the first message of the conversation (for auto titling)
    existing_messages=(
        client.table("messages")
        .select("id").eq("conversation_id",conversation_id).limit(1).execute()
    )
    is_first_message=len(existing_messages.data)==0

    # 2. Save the user's message first
    client.table("messages").insert(
        {"conversation_id": conversation_id, "role": "user", "content": body.question}
    ).execute()

    if not document_ids:
        answer_text = "You don't have any processed documents yet to answer this from. Upload a document first."
        assistant_row = (
            client.table("messages")
            .insert(
                {
                    "conversation_id": conversation_id,
                    "role": "assistant",
                    "content": answer_text,
                    "is_answerable": False,
                }
            )
            .execute()
        ).data[0]
        return {**assistant_row, "citations": []}

    # 3. Retrieve -> generate
    chunks = retrieve(document_ids, body.question)
    result = generate_answer(body.question, chunks)

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