"""Tests for conversations API — services mocked, no network calls."""
from __future__ import annotations

from collections.abc import Generator
from datetime import datetime, timezone
from unittest.mock import MagicMock, patch

import pytest
from fastapi import HTTPException
from fastapi.testclient import TestClient

from app.core.auth import get_current_user
from app.main import create_app
from app.models.conversation import Conversation, Message
from app.models.user import User

UTC = timezone.utc
_NOW = datetime(2024, 6, 1, 12, 0, 0, tzinfo=UTC)
_NOW_ISO = "2024-06-01T12:00:00Z"
_USER = User(uid="uid_abc", email="test@example.com", display_name=None, photo_url=None)
_CONV_ID = "conv-uuid-0001"
_MSG_ID = "msg-uuid-0001"


def _make_conv(**overrides: object) -> Conversation:
    base: dict[str, object] = {
        "id": _CONV_ID,
        "owner_uid": "uid_abc",
        "title": "Case Review",
        "created_at": _NOW,
        "updated_at": _NOW,
        "last_message_at": None,
    }
    base.update(overrides)
    return Conversation(**base)  # type: ignore[arg-type]


def _make_msg(**overrides: object) -> Message:
    base: dict[str, object] = {
        "id": _MSG_ID,
        "role": "user",
        "content": "What does clause 3 mean?",
        "created_at": _NOW,
    }
    base.update(overrides)
    return Message(**base)  # type: ignore[arg-type]


@pytest.fixture
def client() -> Generator[TestClient, None, None]:
    app = create_app()
    app.dependency_overrides[get_current_user] = lambda: _USER
    with TestClient(app) as c:
        yield c


# ---------------------------------------------------------------------------
# POST /api/conversations/
# ---------------------------------------------------------------------------

def test_create_conversation_returns_201(client: TestClient) -> None:
    with patch("app.api.conversations.create_conversation") as mc:
        mc.return_value = _make_conv()
        response = client.post("/api/conversations/", json={"title": "Case Review"})
    assert response.status_code == 201


def test_create_conversation_response_shape(client: TestClient) -> None:
    with patch("app.api.conversations.create_conversation") as mc:
        mc.return_value = _make_conv()
        response = client.post("/api/conversations/", json={"title": "Case Review"})
    body = response.json()
    assert isinstance(body["id"], str)
    assert body["title"] == "Case Review"
    assert isinstance(body["created_at"], str)
    assert isinstance(body["updated_at"], str)
    assert body["last_message_at"] is None


def test_create_conversation_timestamps_end_in_z(client: TestClient) -> None:
    with patch("app.api.conversations.create_conversation") as mc:
        mc.return_value = _make_conv()
        response = client.post("/api/conversations/", json={"title": "Case Review"})
    body = response.json()
    assert body["created_at"].endswith("Z")
    assert body["updated_at"].endswith("Z")


def test_create_conversation_excludes_owner_uid(client: TestClient) -> None:
    with patch("app.api.conversations.create_conversation") as mc:
        mc.return_value = _make_conv()
        response = client.post("/api/conversations/", json={"title": "Case Review"})
    assert "owner_uid" not in response.json()


def test_create_conversation_passes_title_to_service(client: TestClient) -> None:
    with patch("app.api.conversations.create_conversation") as mc:
        mc.return_value = _make_conv(title="Discovery Notes")
        client.post("/api/conversations/", json={"title": "Discovery Notes"})
    created: Conversation = mc.call_args.args[0]
    assert created.title == "Discovery Notes"


def test_create_conversation_assigns_owner_uid(client: TestClient) -> None:
    with patch("app.api.conversations.create_conversation") as mc:
        mc.return_value = _make_conv()
        client.post("/api/conversations/", json={"title": "Case Review"})
    created: Conversation = mc.call_args.args[0]
    assert created.owner_uid == "uid_abc"


def test_create_conversation_requires_auth() -> None:
    app = create_app()
    with TestClient(app) as unauthenticated:
        response = unauthenticated.post("/api/conversations/", json={"title": "Test"})
    assert response.status_code == 401


# ---------------------------------------------------------------------------
# GET /api/conversations/
# ---------------------------------------------------------------------------

def test_list_conversations_returns_200(client: TestClient) -> None:
    with patch("app.api.conversations.list_conversations") as ml:
        ml.return_value = [_make_conv()]
        response = client.get("/api/conversations/")
    assert response.status_code == 200


def test_list_conversations_returns_list(client: TestClient) -> None:
    with patch("app.api.conversations.list_conversations") as ml:
        ml.return_value = [_make_conv()]
        response = client.get("/api/conversations/")
    assert isinstance(response.json(), list)
    assert len(response.json()) == 1


def test_list_conversations_empty(client: TestClient) -> None:
    with patch("app.api.conversations.list_conversations") as ml:
        ml.return_value = []
        response = client.get("/api/conversations/")
    assert response.json() == []


def test_list_conversations_excludes_owner_uid(client: TestClient) -> None:
    with patch("app.api.conversations.list_conversations") as ml:
        ml.return_value = [_make_conv()]
        response = client.get("/api/conversations/")
    assert "owner_uid" not in response.json()[0]


def test_list_conversations_limit_capped_at_100(client: TestClient) -> None:
    with patch("app.api.conversations.list_conversations") as ml:
        ml.return_value = []
        client.get("/api/conversations/?limit=999")
    args = ml.call_args
    limit_arg = args.args[1] if len(args.args) > 1 else args.kwargs.get("limit")
    assert limit_arg == 100


def test_list_conversations_requires_auth() -> None:
    app = create_app()
    with TestClient(app) as unauthenticated:
        response = unauthenticated.get("/api/conversations/")
    assert response.status_code == 401


# ---------------------------------------------------------------------------
# GET /api/conversations/{conv_id}
# ---------------------------------------------------------------------------

def test_get_conversation_returns_200(client: TestClient) -> None:
    with patch("app.api.conversations.get_conversation") as mg:
        mg.return_value = _make_conv()
        response = client.get(f"/api/conversations/{_CONV_ID}")
    assert response.status_code == 200


def test_get_conversation_response_shape(client: TestClient) -> None:
    with patch("app.api.conversations.get_conversation") as mg:
        mg.return_value = _make_conv()
        response = client.get(f"/api/conversations/{_CONV_ID}")
    body = response.json()
    assert body["id"] == _CONV_ID
    assert body["title"] == "Case Review"
    assert "owner_uid" not in body


def test_get_conversation_not_found_returns_404(client: TestClient) -> None:
    with patch("app.api.conversations.get_conversation") as mg:
        mg.side_effect = HTTPException(status_code=404, detail="Conversation not found.")
        response = client.get("/api/conversations/missing-id")
    assert response.status_code == 404


def test_get_conversation_requires_auth() -> None:
    app = create_app()
    with TestClient(app) as unauthenticated:
        response = unauthenticated.get(f"/api/conversations/{_CONV_ID}")
    assert response.status_code == 401


# ---------------------------------------------------------------------------
# DELETE /api/conversations/{conv_id}
# ---------------------------------------------------------------------------

def test_delete_conversation_returns_204(client: TestClient) -> None:
    with patch("app.api.conversations.delete_conversation") as md:
        md.return_value = None
        response = client.delete(f"/api/conversations/{_CONV_ID}")
    assert response.status_code == 204


def test_delete_conversation_calls_service(client: TestClient) -> None:
    with patch("app.api.conversations.delete_conversation") as md:
        md.return_value = None
        client.delete(f"/api/conversations/{_CONV_ID}")
    md.assert_called_once_with(_CONV_ID, "uid_abc")


def test_delete_conversation_not_found_returns_404(client: TestClient) -> None:
    with patch("app.api.conversations.delete_conversation") as md:
        md.side_effect = HTTPException(status_code=404, detail="Conversation not found.")
        response = client.delete("/api/conversations/missing-id")
    assert response.status_code == 404


def test_delete_conversation_requires_auth() -> None:
    app = create_app()
    with TestClient(app) as unauthenticated:
        response = unauthenticated.delete(f"/api/conversations/{_CONV_ID}")
    assert response.status_code == 401


# POST /{conv_id}/messages moved to chat.py (SSE); tested in test_m45_hardening.py

def test_create_message_requires_auth() -> None:
    app = create_app()
    with TestClient(app) as unauthenticated:
        response = unauthenticated.post(
            f"/api/conversations/{_CONV_ID}/messages",
            json={"content": "Hello"},
        )
    assert response.status_code == 401


# ---------------------------------------------------------------------------
# GET /api/conversations/{conv_id}/messages
# ---------------------------------------------------------------------------

def test_list_messages_returns_200(client: TestClient) -> None:
    with patch("app.api.conversations.list_messages") as ml:
        ml.return_value = [_make_msg()]
        response = client.get(f"/api/conversations/{_CONV_ID}/messages")
    assert response.status_code == 200


def test_list_messages_returns_list(client: TestClient) -> None:
    with patch("app.api.conversations.list_messages") as ml:
        ml.return_value = [_make_msg()]
        response = client.get(f"/api/conversations/{_CONV_ID}/messages")
    assert isinstance(response.json(), list)
    assert len(response.json()) == 1


def test_list_messages_empty(client: TestClient) -> None:
    with patch("app.api.conversations.list_messages") as ml:
        ml.return_value = []
        response = client.get(f"/api/conversations/{_CONV_ID}/messages")
    assert response.json() == []


def test_list_messages_response_shape(client: TestClient) -> None:
    with patch("app.api.conversations.list_messages") as ml:
        ml.return_value = [_make_msg()]
        response = client.get(f"/api/conversations/{_CONV_ID}/messages")
    msg = response.json()[0]
    assert msg["id"] == _MSG_ID
    assert msg["role"] == "user"
    assert msg["content"] == "What does clause 3 mean?"
    assert msg["created_at"].endswith("Z")


def test_list_messages_limit_capped_at_200(client: TestClient) -> None:
    with patch("app.api.conversations.list_messages") as ml:
        ml.return_value = []
        client.get(f"/api/conversations/{_CONV_ID}/messages?limit=9999")
    args = ml.call_args
    limit_arg = args.args[2] if len(args.args) > 2 else args.kwargs.get("limit")
    assert limit_arg == 200


def test_list_messages_not_found_returns_404(client: TestClient) -> None:
    with patch("app.api.conversations.list_messages") as ml:
        ml.side_effect = HTTPException(status_code=404, detail="Conversation not found.")
        response = client.get("/api/conversations/missing/messages")
    assert response.status_code == 404


def test_list_messages_requires_auth() -> None:
    app = create_app()
    with TestClient(app) as unauthenticated:
        response = unauthenticated.get(f"/api/conversations/{_CONV_ID}/messages")
    assert response.status_code == 401
