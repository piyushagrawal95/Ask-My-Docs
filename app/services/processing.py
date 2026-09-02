from app.database import get_service_client
from app.services.extraction import extract_text, ExtractionError
from app.services.chunking import chunk_pages
from app.services.embeddings import embed_texts

class ProcessingError(Exception):
    pass

def process_document(document_id:str, file_bytes:bytes, file_name:str) -> None:
    client=get_service_client()

    try:
        client.table("documents").update({"status":"processing"}).eq("id",document_id).execute()
        pages=extract_text(file_bytes,file_name)
        chunks=chunk_pages(pages)
        if not chunks:
            raise ProcessingError("No chunks produced from document content")

        ## Clear old chunks (Safe for Reprocessing)
        client.table("document_chunks").delete().eq("document_id",document_id).execute()

        ## Embed all chunks
        embeddings=embed_texts([c.content for c in chunks]) 

        ## Insert chunk rows
        rows=[{
            "document_id":document_id,
            "content":c.content,
            "chunk_index":c.chunk_index,
            "page_number":c.page_number,
            "embedding":emb,
        }
        for c,emb in zip(chunks,embeddings)
        ]
        client.table("document_chunks").insert(rows).execute()

        client.table("documents").update({"status":"ready","error_message":None}).eq("id",document_id).execute()

    except(ExtractionError,ProcessingError) as e:
        client.table("documents").update({"status":"failed","error_message":str(e)}).eq("id",document_id).execute()

    except Exception as e:
        client.table("documents").update({"status":"failed","error_message":f"Unexpected error:{e}"}).eq("id",document_id).execute()