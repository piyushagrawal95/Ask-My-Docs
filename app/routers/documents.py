from fastapi import APIRouter, BackgroundTasks, Depends, UploadFile, File, Form, HTTPException
from app.auth import get_current_user, CurrentUser
from app.database import get_service_client
from app.services.processing import process_document
from app.config import settings

router = APIRouter(prefix="/documents", tags=["documents"])

ALLOWED_EXTENSIONS = {ext.strip().lower() for ext in settings.allowed_extensions.split(",")}
MAX_FILE_SIZE_BYTES = settings.max_file_size_mb * 1024 * 1024


def _get_owned_conversation_id(client, conversation_id: str, user_id: str) -> str:
    """Confirms the conversation exists and belongs to this user, else 404."""
    resp = (
        client.table("conversations")
        .select("id")
        .eq("id", conversation_id)
        .eq("owner_id", user_id)
        .execute()
    )
    if not resp.data:
        raise HTTPException(status_code=404, detail="Conversation not found.")
    return conversation_id


@router.post("", status_code=201)
async def upload_document(
    background_tasks: BackgroundTasks,
    file: UploadFile = File(...),
    conversation_id: str = Form(...),
    user: CurrentUser = Depends(get_current_user),
):
    client_for_check = get_service_client()
    _get_owned_conversation_id(client_for_check, conversation_id, user.id)

    # 1. Extension check
    ext = file.filename.lower().rsplit(".", 1)[-1] if "." in file.filename else ""
    if ext not in ALLOWED_EXTENSIONS:
        raise HTTPException(
            status_code=400,
            detail=f"Unsupported file type. Allowed: {', '.join(ALLOWED_EXTENSIONS)}",
        )

    # 2. File read karo bytes mein
    file_bytes = await file.read()
    if not file_bytes:
        raise HTTPException(status_code=400, detail="Uploaded file is empty.")

    warning = None
    if len(file_bytes) > MAX_FILE_SIZE_BYTES:
        warning = f"File is larger than {MAX_FILE_SIZE_BYTES // (1024 * 1024)}MB — processing may take longer."

    # 3. documents table mein row banao (status = pending)
    client = get_service_client()
    storage_path = f"{user.id}/{conversation_id}/{file.filename}"

    insert_resp = (
        client.table("documents")
        .insert(
            {
                "owner_id": user.id,
                "conversation_id": conversation_id,
                "file_name": file.filename,
                "storage_path": storage_path,
                "status": "pending",
            }
        )
        .execute()
    )
    document = insert_resp.data[0]

    # 4. Storage mein actual file upload karo
    try:
        client.storage.from_("documents").upload(storage_path, file_bytes)
    except Exception as e:
        error_text = str(e)
        is_duplicate = "already exists" in error_text.lower() or "409" in error_text or "Duplicate" in error_text

        if is_duplicate:
            client.table("documents").delete().eq("id", document["id"]).execute()
            raise HTTPException(
                status_code=409,
                detail="A file with this name already exists. Please rename the file or delete the existing one first.",
            )

        client.table("documents").update(
            {"status": "failed", "error_message": f"Storage upload failed: {error_text}"}
        ).eq("id", document["id"]).execute()
        raise HTTPException(status_code=502, detail="Failed to store file. Please try again.")

    # 5. Processing background mein trigger karo
    background_tasks.add_task(process_document, document["id"], file_bytes, file.filename)

    return {**document, "warning": warning}


@router.get("")
async def list_documents(conversation_id: str, user: CurrentUser = Depends(get_current_user)):
    client = get_service_client()
    resp = (
        client.table("documents")
        .select("*")
        .eq("owner_id", user.id)
        .eq("conversation_id", conversation_id)
        .order("created_at", desc=True)
        .execute()
    )
    return {"documents": resp.data}


@router.get("/{document_id}")
async def get_document(document_id: str, user: CurrentUser = Depends(get_current_user)):
    client = get_service_client()
    resp = (
        client.table("documents")
        .select("*")
        .eq("id", document_id)
        .eq("owner_id", user.id)
        .execute()
    )
    if not resp.data:
        raise HTTPException(status_code=404, detail="Document not found.")
    return resp.data[0]


@router.delete("/{document_id}", status_code=204)
async def delete_document(document_id: str, user: CurrentUser = Depends(get_current_user)):
    client = get_service_client()
    resp = (
        client.table("documents")
        .select("id, storage_path")
        .eq("id", document_id)
        .eq("owner_id", user.id)
        .execute()
    )
    if not resp.data:
        raise HTTPException(status_code=404, detail="Document not found.")

    storage_path = resp.data[0]["storage_path"]

    try:
        client.storage.from_("documents").remove([storage_path])
    except Exception:
        pass

    client.table("documents").delete().eq("id", document_id).execute()
    return None