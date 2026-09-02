from unittest.mock import MagicMock,patch

def test_upload_rejects_unsupported_extension(client):
    resp=client.post("/documents",files={"file":("notes.exe",b"some bytes","application/octet-stream")},)
    assert resp.status_code==400
    assert "Unsupported file type" in resp.json()["detail"]

def test_upload_rejects_empty_file(client):
    resp=client.post("/documents",files={"file":("notes.txt",b"","text/plain")},)
    assert resp.status_code==400
    assert "empty" in resp.json()["detail"].lower()

@patch("app.routers.documents.process_document")
@patch("app.routers.documents.get_service_client")
def test_upload_success_triggers_processing(mock_get_client,mock_process,client):
    mock_client=MagicMock()
    mock_get_client.return_value=mock_client
    mock_client.table.return_value.insert.return_value.execute.return_value.data=[{
        "id":"doc-1",
        "owner_id":"11111111-1111-1111-1111-111111111111",
        "file_name":"notes.txt",
        "storage_path":"u/notes.txt",
        "status":"pending",
        "error_message":None,
        "page_count":None,
        "created_at": "2026-01-01T00:00:00Z",
        "updated_at": "2026-01-01T00:00:00Z",
    }]

    resp=client.post("/documents",files={"file":("notes.txt",b"hello world","text/plain")},)

    assert resp.status_code==201
    assert resp.json()["status"]=="pending"
    mock_process.assert_called_once()


@patch("app.routers.documents.get_service_client")
def test_get_document_not_found(mock_get_client,client):
    mock_client=MagicMock()
    mock_get_client.return_value=mock_client
    mock_client.table.return_value.select.return_value.eq.return_value.eq.return_value.execute.return_value.data = []

    resp=client.get("/documents/does-not-exist")
    assert resp.status_code==404