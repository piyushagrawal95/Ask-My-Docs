from fastapi import APIRouter, BackgroundTasks, Depends, UploadFile, File, HTTPException
from app.auth import get_current_user, CurrentUser
from app.database import get_service_client
from app.services.processing import process_document

router = APIRouter(prefix="/documents", tags=["documents"])

ALLOWED_EXTENSIONS = {"pdf", "docx", "txt"}
MAX_FILE_SIZE_BYTES=10*1024*1024 #10 MB

@router.post("", status_code=201)
async def upload_document(
    background_tasks: BackgroundTasks,
    file: UploadFile = File(...),
    user: CurrentUser = Depends(get_current_user),
):
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

    client=get_service_client()
    existing=(
        client.table("documents").select("id","status").eq("owner_id",user.id).eq("file_name",file.filename).execute()
    )
    warning=None
    if existing.data:
        warning=(f"You already have a document named '{file.filename}'"
                 f"({len(existing.data)} existing copy/copies).This will be uploaded as a new, separated document."
        )


    # 3. documents table mein row banao (status = pending)
    storage_path = f"{user.id}/{file.filename}"

    insert_resp = (
        client.table("documents")
        .insert(
            {
                "owner_id": user.id,
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
        client.table("documents").update(
            {"status": "failed", "error_message": f"Storage upload failed: {e}"}
        ).eq("id", document["id"]).execute()
        raise HTTPException(status_code=502, detail=f"Failed to store file: {e}")

    # 5. Processing background mein trigger karo (upload request turant return ho jayega,
    #    processing background mein chalti rahegi)
    background_tasks.add_task(process_document, document["id"], file_bytes, file.filename)

    return {**document,"warning":warning}


@router.get("")
async def list_documents(user: CurrentUser = Depends(get_current_user)):
    client = get_service_client()
    resp = (
        client.table("documents")
        .select("*")
        .eq("owner_id", user.id)
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
        .select("id")
        .eq("id", document_id)
        .eq("owner_id", user.id)
        .execute()
    )
    if not resp.data:
        raise HTTPException(status_code=404, detail="Document not found.")

    client.table("documents").delete().eq("id", document_id).execute()
    return None


@router.post("/{document_id}/reprocess",status_code=202)
async def reprocess_document(
    document_id:str,
    background_tasks:BackgroundTasks,
    user:CurrentUser=Depends(get_current_user),
):
    client=get_service_client()
    resp=(client.table("documents").select("id,storage_path,file_name").eq("id",document_id).eq("owner_id",user.id).execute())
    if not resp.data:
        raise HTTPException(status_code=404,detail="Document not found")

    document=resp.data[0]
    # Redownload the original file from storage
    try:
        file_bytes=client.storage.from_("documents").download(document["storage_path"])
    except Exception as e:
        raise HTTPException(status_code=502, detail=f"Could not fetch stored file:{e}")

    client.table("documents").update({
        "status":"pending","error_message":None
    }).eq("id",document_id).execute()

    background_tasks.add_task(process_document,document_id,file_bytes,document["file_name"])
    return {"id":document_id,"status":"pending","message":"Reprocessing started"}
