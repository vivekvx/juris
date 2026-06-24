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
