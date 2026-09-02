import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))

from app.database import get_service_client
from app.services.embeddings import embed_query
from app.services.retrieval import vector_search, bm25_search, retrieve

# Fill this in with the document_id of RAG_Test_Document_Large.pdf
# (grab it from the "documents" table in Supabase, or print it inside setup_documents)
DOCUMENT_ID = "2431ebb9-276e-4df6-b9b0-026e1193d1a3"

QUESTIONS = [
    "What embedding model is referenced in the appendix test data?",
    "What error code is shown in the appendix test data table?",
    "What chunk overlap percentage is set in the configuration shown in the appendix?",
]

for q in QUESTIONS:
    print(f"\n===== {q} =====")
    emb = embed_query(q)

    v = vector_search([DOCUMENT_ID], emb, k=20)
    print(f"vector_search returned {len(v)} candidates")
    for c in v[:10]:
        print(f"  page={c.page_number} score={c.score:.4f} preview={c.content[:60]!r}")

    b = bm25_search([DOCUMENT_ID], q, k=20)
    print(f"bm25_search returned {len(b)} candidates")
    for c in b[:10]:
        print(f"  page={c.page_number} score={c.score:.4f} preview={c.content[:60]!r}")

    final = retrieve([DOCUMENT_ID], q, top_k=10)
    print(f"final retrieve() (after hybrid+rerank) returned {len(final)} candidates")
    for c in final:
        print(f"  page={c.page_number} score={c.score:.4f} preview={c.content[:60]!r}")


resp = get_service_client().rpc(
    "search_document_chunks_bm25",
    {
        "p_document_ids": [DOCUMENT_ID],
        "p_query": "error code",
        "p_match_count": 20,
    },
).execute()

print("raw response data:", resp.data)
print("raw response (full):", resp)