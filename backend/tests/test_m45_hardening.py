"""Tests for M4.5 hardening fixes — no network/Firestore calls."""
from __future__ import annotations

from datetime import datetime, timezone
from unittest.mock import MagicMock, patch

import pytest

UTC = timezone.utc
_T0 = datetime(2024, 6, 1, 12, 0, 0, tzinfo=UTC)


def _make_msg_snap(msg_id: str, created_offset_secs: int) -> MagicMock:
    from datetime import timedelta
    snap = MagicMock()
    snap.exists = True
    snap.to_dict.return_value = {
        "id": msg_id,
        "role": "user",
        "content": f"msg {msg_id}",
        "created_at": _T0 + timedelta(seconds=created_offset_secs),
    }
    return snap


def test_list_messages_tail_returns_latest_in_chrono_order() -> None:
    """tail=True should return last N messages in ascending created_at order."""
    from app.services.conversations import list_messages

    with patch("app.services.conversations.get_firestore_client") as mock_get:
        mock_db = MagicMock()
        mock_get.return_value = mock_db

        conv_snap = MagicMock()
        conv_snap.exists = True
        conv_snap.to_dict.return_value = {
            "id": "conv_001", "owner_uid": "uid_abc", "title": "T",
            "created_at": _T0, "updated_at": _T0, "last_message_at": None,
        }
        conv_ref = MagicMock()
        conv_ref.get.return_value = conv_snap

        # Firestore returns DESC order: newest first
        msg_snaps = [_make_msg_snap("msg_3", 3), _make_msg_snap("msg_2", 2)]
        messages_coll = MagicMock()
        messages_coll.order_by.return_value.limit.return_value.stream.return_value = msg_snaps
        conv_ref.collection.return_value = messages_coll
        mock_db.collection.return_value.document.return_value = conv_ref

        msgs = list_messages("conv_001", "uid_abc", limit=2, tail=True)

        # order_by called with DESCENDING
        messages_coll.order_by.assert_called_once()
        call_args = messages_coll.order_by.call_args
        assert "DESCENDING" in str(call_args)

        # Result is chronological (oldest first after reversal)
        assert msgs[0].id == "msg_2"
        assert msgs[1].id == "msg_3"


def test_list_messages_default_returns_oldest_first() -> None:
    """tail=False (default) preserves existing behaviour — oldest first."""
    from app.services.conversations import list_messages

    with patch("app.services.conversations.get_firestore_client") as mock_get:
        mock_db = MagicMock()
        mock_get.return_value = mock_db

        conv_snap = MagicMock()
        conv_snap.exists = True
        conv_snap.to_dict.return_value = {
            "id": "conv_001", "owner_uid": "uid_abc", "title": "T",
            "created_at": _T0, "updated_at": _T0, "last_message_at": None,
        }
        conv_ref = MagicMock()
        conv_ref.get.return_value = conv_snap

        msg_snaps = [_make_msg_snap("msg_1", 1), _make_msg_snap("msg_2", 2)]
        messages_coll = MagicMock()
        messages_coll.order_by.return_value.limit.return_value.stream.return_value = msg_snaps
        conv_ref.collection.return_value = messages_coll
        mock_db.collection.return_value.document.return_value = conv_ref

        msgs = list_messages("conv_001", "uid_abc", limit=50, tail=False)

        call_args = messages_coll.order_by.call_args
        assert "DESCENDING" not in str(call_args)
        assert msgs[0].id == "msg_1"
        assert msgs[1].id == "msg_2"


# ---------------------------------------------------------------------------
# Fix 2: Ownership check before StreamingResponse
# ---------------------------------------------------------------------------

def test_send_message_returns_404_before_streaming_for_wrong_owner() -> None:
    """Wrong-owner conv must 404 cleanly, not open a stream then abort."""
    from fastapi import HTTPException
    from fastapi.testclient import TestClient
    from app.main import create_app
    from app.core.auth import get_current_user

    with patch("app.api.chat.get_conversation") as mock_get_conv:
        mock_get_conv.side_effect = HTTPException(status_code=404, detail="Conversation not found.")

        app = create_app()
        app.dependency_overrides[get_current_user] = lambda: MagicMock(uid="uid_attacker")
        test_client = TestClient(app)
        resp = test_client.post(
            "/api/conversations/conv_victim/messages",
            json={"content": "hello"},
        )
        assert resp.status_code == 404
        assert "text/event-stream" not in resp.headers.get("content-type", "")


# ---------------------------------------------------------------------------
# Fix 3: Embed failure hard-fails; retrieve takes pre-embedded vector
# ---------------------------------------------------------------------------

def test_retrieve_signature_accepts_query_vec() -> None:
    """rag.retrieve must accept query_vec (list[float]), not a query string."""
    import inspect
    from app.services.rag import retrieve
    sig = inspect.signature(retrieve)
    params = list(sig.parameters.keys())
    assert "query_vec" in params, f"Expected query_vec param, got: {params}"
    assert "query" not in params, f"Old 'query' string param still present: {params}"


@pytest.mark.asyncio
async def test_embed_failure_yields_error_no_user_message_written() -> None:
    """If embed_query raises, no user message is written and SSE error is yielded."""
    from app.api.chat import _stream
    from app.models.conversation import Conversation

    conv = Conversation(
        id="conv_001", owner_uid="uid_abc", title="T",
        created_at=_T0, updated_at=_T0,
    )

    with patch("app.api.chat.embed_query", side_effect=RuntimeError("quota exceeded")), \
         patch("app.api.chat.create_message") as mock_create_msg, \
         patch("app.api.chat.list_messages", return_value=[]):

        events = []
        async for chunk in _stream(conv, "test query", None, "uid_abc"):
            events.append(chunk)

        mock_create_msg.assert_not_called()
        assert any("event: error" in e for e in events)
        assert not any("event: token" in e for e in events)


# ---------------------------------------------------------------------------
# Fix 4: Disconnect — CancelledError does not write orphan assistant message
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_cancelled_error_does_not_write_assistant_message() -> None:
    """CancelledError (client disconnect) must not persist a partial assistant message."""
    import asyncio
    from app.api.chat import _stream
    from app.models.conversation import Conversation

    conv = Conversation(
        id="conv_001", owner_uid="uid_abc", title="T",
        created_at=_T0, updated_at=_T0,
    )

    async def _cancelling_stream(*args, **kwargs):
        yield "partial token"
        raise asyncio.CancelledError("client gone")

    with patch("app.api.chat.embed_query", return_value=[0.1] * 768), \
         patch("app.api.chat.create_message"), \
         patch("app.api.chat.retrieve", return_value=[]), \
         patch("app.api.chat.stream_response", side_effect=_cancelling_stream), \
         patch("app.api.chat.create_assistant_message") as mock_create_asst, \
         patch("app.api.chat.list_messages", return_value=[]):

        with pytest.raises(asyncio.CancelledError):
            async for _ in _stream(conv, "test", None, "uid_abc"):
                pass

        mock_create_asst.assert_not_called()


@pytest.mark.asyncio
async def test_llm_error_with_content_writes_partial_message() -> None:
    """Non-disconnect LLM error with accumulated content must persist partial message."""
    from app.api.chat import _stream
    from app.models.conversation import Conversation

    conv = Conversation(
        id="conv_001", owner_uid="uid_abc", title="T",
        created_at=_T0, updated_at=_T0,
    )

    async def _failing_stream(*args, **kwargs):
        yield "some text"
        raise RuntimeError("quota exceeded")

    with patch("app.api.chat.embed_query", return_value=[0.1] * 768), \
         patch("app.api.chat.create_message"), \
         patch("app.api.chat.retrieve", return_value=[]), \
         patch("app.api.chat.stream_response", side_effect=_failing_stream), \
         patch("app.api.chat.create_assistant_message") as mock_create_asst, \
         patch("app.api.chat.list_messages", return_value=[]):

        events = [e async for e in _stream(conv, "test", None, "uid_abc")]

        mock_create_asst.assert_called_once()
        call_content = mock_create_asst.call_args[0][2]
        assert "[Response interrupted]" in call_content
        assert any("event: error" in e for e in events)
