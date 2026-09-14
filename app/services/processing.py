import gc
import time
import logging
from app.database import get_service_client
from app.services.extraction import extract_text, ExtractionError
from app.services.chunking import chunk_pages
from app.services.embeddings import embed_texts

logger = logging.getLogger("processing")

class ProcessingError(Exception):
    pass

def process_document(document_id:str, file_bytes:bytes, file_name:str) -> None:
    client=get_service_client()

    try:
        client.table("documents").update({"status":"processing"}).eq("id",document_id).execute()

        t0=time.perf_counter()
        pages=extract_text(file_bytes,file_name)
        page_count = len(pages)
        logger.warning(f"[{document_id}] extract_text: {time.perf_counter()-t0:.1f}s, {page_count} pages")
        del file_bytes  # no longer needed once text is extracted

        t0=time.perf_counter()
        chunks=chunk_pages(pages)
        logger.warning(f"[{document_id}] chunk_pages: {time.perf_counter()-t0:.1f}s, {len(chunks)} chunks")
        del pages
        if not chunks:
            raise ProcessingError("No chunks produced from document content")

        ## Clear old chunks (Safe for Reprocessing)
        client.table("document_chunks").delete().eq("document_id",document_id).execute()

        ## Embed all chunks (processed internally in small batches)
        t0=time.perf_counter()
        embeddings=embed_texts([c.content for c in chunks])
        logger.warning(f"[{document_id}] embed_texts: {time.perf_counter()-t0:.1f}s")

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
        del chunks, embeddings
        gc.collect()

        ## Insert chunk rows in batches of 50
        BATCH_INSERT_SIZE = 50
        for i in range(0, len(rows), BATCH_INSERT_SIZE):
            client.table("document_chunks").insert(rows[i : i + BATCH_INSERT_SIZE]).execute()

        client.table("documents").update({"status":"ready","error_message":None}).eq("id",document_id).execute()

    except(ExtractionError,ProcessingError) as e:
        client.table("documents").update({"status":"failed","error_message":str(e)}).eq("id",document_id).execute()

    except Exception as e:
        client.table("documents").update({"status":"failed","error_message":f"Unexpected error:{e}"}).eq("id",document_id).execute()
    finally:
        gc.collect()