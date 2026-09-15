import sys
import json
from pathlib import Path

# Project root ko path me add karo taaki "app.*" imports kaam karein
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
from app.database import get_service_client
from app.services.processing import process_document
from app.services.retrieval import retrieve
from app.services.generation import generate_answer

EVAL_DIR = Path(__file__).resolve().parent
FIXTURES_DIR = EVAL_DIR / "fixtures"
DATASET_PATH = EVAL_DIR / "eval_dataset.json"

TEST_USER_EMAIL = "eval-fixture-user@askmydocs.internal"

ANSWER_CORRECTNESS_THRESHOLD = 0.7
RETRIEVAL_ACCURACY_THRESHOLD = 0.7


def get_or_create_test_user(client) -> str:
    """Ensures a fixture auth user exists in whichever Supabase project this
    is running against (local dev or CI), and returns its id. Needed because
    `documents.owner_id` has a foreign key onto auth.users - a hardcoded UUID
    only works on the one project it happened to be created on."""
    page = 1
    while True:
        resp = client.auth.admin.list_users(page=page, per_page=200)
        users = resp if isinstance(resp, list) else getattr(resp, "users", [])
        if not users:
            break
        for u in users:
            if u.email == TEST_USER_EMAIL:
                return u.id
        page += 1

    created = client.auth.admin.create_user(
        {
            "email": TEST_USER_EMAIL,
            "password": "eval-fixture-password-not-used-anywhere",
            "email_confirm": True,
        }
    )
    return created.user.id


def setup_documents(client, dataset, test_user_id):
    """Upload + process each fixture document once. Returns {filename: document_id}."""
    doc_ids = {}
    for filename in dataset["fixture_documents"]:
        file_bytes = (FIXTURES_DIR / filename).read_bytes()

        insert_resp = (
            client.table("documents")
            .insert(
                {
                    "owner_id": test_user_id,
                    "file_name": filename,
                    "storage_path": f"eval/{filename}",
                    "status": "pending",
                }
            )
            .execute()
        )
        document_id = insert_resp.data[0]["id"]

        # Synchronous call (no background_tasks here) - waits till chunks are stored.
        process_document(document_id, file_bytes, filename)

        status = client.table("documents").select("status,error_message").eq("id", document_id).execute().data[0]
        if status["status"] != "ready":
            raise RuntimeError(f"Failed to process {filename}: {status['error_message']}")

        doc_ids[filename] = document_id
    return doc_ids


def cleanup_documents(client, doc_ids):
    for document_id in doc_ids.values():
        client.table("document_chunks").delete().eq("document_id", document_id).execute()
        client.table("documents").delete().eq("id", document_id).execute()


def keyword_score(answer_text, expected_keywords):
    """Simple recall of expected keywords in the generated answer. Swap for an LLM-judge later if needed."""
    if not expected_keywords:
        return 1.0
    text_lower = answer_text.lower()
    hits = sum(1 for kw in expected_keywords if kw.lower() in text_lower)
    return hits / len(expected_keywords)


def run_case(case, doc_ids):
    if case["source_document"]:
        search_doc_ids = [doc_ids[case["source_document"]]]
    else:
        # Unanswerable case: no single source doc, so search across all fixtures -
        # the system should correctly find nothing relevant in either one.
        search_doc_ids = list(doc_ids.values())

    chunks = retrieve(search_doc_ids, case["question"], top_k=5)
    result = generate_answer(case["question"], chunks)

    row = {
        "id": case["id"],
        "question": case["question"],
        "expected_answerable": case["is_answerable"],
        "got_answerable": result.is_answerable,
        "answer": result.answer,
        "retrieved_pages": [c.page_number for c in chunks],
    }

    if case["is_answerable"]:
        expected_page = case.get("source_page")
        row["retrieval_hit"] = (
            expected_page in row["retrieved_pages"] if expected_page else len(chunks) > 0
        )
        row["answer_score"] = keyword_score(result.answer, case.get("expected_keywords", []))
        row["citation_ok"] = bool(result.citations) and result.is_answerable
        row["hallucinated"] = False
    else:
        row["retrieval_hit"] = None
        row["answer_score"] = None
        row["citation_ok"] = None
        # Hallucination = model confidently answered a question it had no grounds to answer.
        row["hallucinated"] = result.is_answerable is True

    return row


def summarize(results):
    answerable = [r for r in results if r["expected_answerable"]]
    unanswerable = [r for r in results if not r["expected_answerable"]]

    def avg(rows, key):
        return sum(bool(r[key]) for r in rows) / len(rows) if rows else 0.0

    retrieval_accuracy = avg(answerable, "retrieval_hit")
    answer_correctness = (
        sum(r["answer_score"] for r in answerable) / len(answerable) if answerable else 0.0
    )
    citation_accuracy = avg(answerable, "citation_ok")
    hallucination_rate = avg(unanswerable, "hallucinated")

    return {
        "retrieval_accuracy": retrieval_accuracy,
        "answer_correctness": answer_correctness,
        "citation_accuracy": citation_accuracy,
        "hallucination_rate": hallucination_rate,
    }


def main():
    dataset = json.loads(DATASET_PATH.read_text())
    client = get_service_client()
    test_user_id = get_or_create_test_user(client)

    print(f"Setting up {len(dataset['fixture_documents'])} fixture document(s)...")
    doc_ids = setup_documents(client, dataset, test_user_id)

    results = []
    try:
        for case in dataset["cases"]:
            print(f"Running {case['id']}: {case['question']}")
            results.append(run_case(case, doc_ids))
    finally:
        cleanup_documents(client, doc_ids)

    metrics = summarize(results)

    print("\n=== Per-case results ===")
    for r in results:
        status = "OK" if r["got_answerable"] == r["expected_answerable"] else "MISMATCH"
        print(f"[{status}] {r['id']}: expected_answerable={r['expected_answerable']} got={r['got_answerable']}")
        if status == "MISMATCH":
            print(f"    retrieved_pages={r['retrieved_pages']}")
            print(f"    answer={r['answer'][:200]!r}")

    print("\n=== Metrics ===")
    for k, v in metrics.items():
        print(f"{k}: {v:.2f}")

    failed = (
        metrics["retrieval_accuracy"] < RETRIEVAL_ACCURACY_THRESHOLD
        or metrics["answer_correctness"] < ANSWER_CORRECTNESS_THRESHOLD
    )
    if failed:
        print("\nEVAL FAILED: quality below threshold.")
        sys.exit(1)

    print("\nEVAL PASSED.")
    sys.exit(0)


if __name__ == "__main__":
    main()