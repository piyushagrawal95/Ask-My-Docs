from unittest.mock import MagicMock, patch


def _make_table_mocks(conversation_row=None, documents_data=None, message_insert_data=None):
    """Alag-alag table() calls ko alag mock deta hai, taaki data collide na ho."""
    conversations_mock = MagicMock()
    conversations_mock.select.return_value.eq.return_value.eq.return_value.execute.return_value.data = (
        [conversation_row] if conversation_row else []
    )

    documents_mock = MagicMock()
    documents_mock.select.return_value.eq.return_value.eq.return_value.execute.return_value.data = documents_data or []

    messages_mock = MagicMock()
    messages_mock.insert.return_value.execute.return_value.data = message_insert_data or []

    citations_mock = MagicMock()

    def table_side_effect(name):
        return {
            "conversations": conversations_mock,
            "documents": documents_mock,
            "messages": messages_mock,
            "citations": citations_mock,
        }[name]

    return table_side_effect, conversations_mock, documents_mock, messages_mock, citations_mock


@patch("app.routers.conversations.get_service_client")
def test_create_conversation(mock_get_client, client):
    mock_client = MagicMock()
    mock_get_client.return_value = mock_client
    mock_client.table.return_value.insert.return_value.execute.return_value.data = [
        {
            "id": "conv-1",
            "user_id": "11111111-1111-1111-1111-111111111111",
            "title": None,
            "created_at": "2026-01-01T00:00:00Z",
            "updated_at": "2026-01-01T00:00:00Z",
        }
    ]

    resp = client.post("/conversations")

    assert resp.status_code == 201
    assert resp.json()["id"] == "conv-1"


@patch("app.routers.conversations.get_service_client")
def test_get_conversation_not_found(mock_get_client, client):
    mock_client = MagicMock()
    mock_get_client.return_value = mock_client
    mock_client.table.return_value.select.return_value.eq.return_value.eq.return_value.execute.return_value.data = []

    resp = client.get("/conversations/does-not-exist")
    assert resp.status_code == 404


@patch("app.routers.conversations.generate_answer")
@patch("app.routers.conversations.retrieve")
@patch("app.routers.conversations.get_service_client")
def test_ask_question_with_no_ready_documents(mock_get_client, mock_retrieve, mock_generate, client):
    mock_client = MagicMock()
    mock_get_client.return_value = mock_client

    table_side_effect, conversations_mock, documents_mock, messages_mock, citations_mock = _make_table_mocks(
        conversation_row={
            "id": "conv-1",
            "user_id": "11111111-1111-1111-1111-111111111111",
            "title": None,
            "created_at": "2026-01-01T00:00:00Z",
            "updated_at": "2026-01-01T00:00:00Z",
        },
        documents_data=[],  # user ke paas koi ready document nahi
        message_insert_data=[
            {
                "id": "msg-1",
                "conversation_id": "conv-1",
                "role": "assistant",
                "content": "You don't have any processed documents yet to answer this from. Upload a document first.",
                "is_answerable": False,
                "created_at": "2026-01-01T00:00:00Z",
            }
        ],
    )
    mock_client.table.side_effect = table_side_effect

    resp = client.post("/conversations/conv-1/messages", json={"question": "What is the revenue?"})

    assert resp.status_code == 201
    assert resp.json()["is_answerable"] is False
    assert resp.json()["citations"] == []
    mock_retrieve.assert_not_called()
    mock_generate.assert_not_called()