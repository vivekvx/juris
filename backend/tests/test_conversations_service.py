"""Tests for conversations service — Firestore mocked, no network calls."""
from __future__ import annotations

from collections.abc import Generator
from datetime import datetime, timedelta, timezone
from unittest.mock import MagicMock, patch

import pytest
from fastapi import HTTPException

from app.models.conversation import Conversation, Message
from app.services.conversations import (
    create_conversation,
    create_message,
    delete_conversation,
    get_conversation,
    list_conversations,
    list_messages,
)

UTC = timezone.utc
_T0 = datetime(2024, 6, 1, 12, 0, 0, tzinfo=UTC)

_CONV_DATA: dict[str, object] = {
    "id": "conv_001",
    "owner_uid": "uid_abc",
    "title": "Case Review",
    "created_at": _T0,
    "updated_at": _T0,
    "last_message_at": None,
}

_MSG_DATA: dict[str, object] = {
    "id": "msg_001",
    "role": "user",
    "content": "What does clause 3 mean?",
    "created_at": _T0,
}


def _conv_data(**overrides: object) -> dict[str, object]:
    d = dict(_CONV_DATA)
    d.update(overrides)
    return d


def _msg_data(**overrides: object) -> dict[str, object]:
    d = dict(_MSG_DATA)
    d.update(overrides)
    return d


def _make_conv(**overrides: object) -> Conversation:
    return Conversation(**_conv_data(**overrides))  # type: ignore[arg-type]


def _make_msg(**overrides: object) -> Message:
    return Message(**_msg_data(**overrides))  # type: ignore[arg-type]


@pytest.fixture
def mock_db() -> Generator[MagicMock, None, None]:
    with patch("app.services.conversations.get_firestore_client") as mock_get:
        mock_client = MagicMock()
        mock_get.return_value = mock_client
        yield mock_client


def _make_conv_ref(mock_db: MagicMock, exists: bool, data: dict[str, object] | None = None) -> MagicMock:
    snap = MagicMock()
    snap.exists = exists
    snap.to_dict.return_value = data if exists else None
    ref = MagicMock()
    ref.get.return_value = snap
    mock_db.collection.return_value.document.return_value = ref
    return ref


def _make_snap(data: dict[str, object]) -> MagicMock:
    snap = MagicMock()
    snap.exists = True
    snap.to_dict.return_value = data
    return snap


# ---------------------------------------------------------------------------
# create_conversation
# ---------------------------------------------------------------------------

def test_create_returns_conversation(mock_db: MagicMock) -> None:
    _make_conv_ref(mock_db, exists=False)
    result = create_conversation(_make_conv())
    assert result.id == "conv_001"
    assert result.title == "Case Review"


def test_create_calls_firestore_set(mock_db: MagicMock) -> None:
    ref = _make_conv_ref(mock_db, exists=False)
    create_conversation(_make_conv())
    ref.set.assert_called_once()


# ---------------------------------------------------------------------------
# get_conversation
# ---------------------------------------------------------------------------

def test_get_returns_conversation(mock_db: MagicMock) -> None:
    _make_conv_ref(mock_db, exists=True, data=_conv_data())
    conv = get_conversation("conv_001", "uid_abc")
    assert conv.id == "conv_001"


def test_get_not_found_raises_404(mock_db: MagicMock) -> None:
    _make_conv_ref(mock_db, exists=False)
    with pytest.raises(HTTPException) as exc:
        get_conversation("missing", "uid_abc")
    assert exc.value.status_code == 404


def test_get_wrong_owner_raises_404(mock_db: MagicMock) -> None:
    _make_conv_ref(mock_db, exists=True, data=_conv_data(owner_uid="uid_abc"))
    with pytest.raises(HTTPException) as exc:
        get_conversation("conv_001", "uid_attacker")
    assert exc.value.status_code == 404


# ---------------------------------------------------------------------------
# list_conversations
# ---------------------------------------------------------------------------

def test_list_returns_conversations_for_owner(mock_db: MagicMock) -> None:
    mock_db.collection.return_value.where.return_value.stream.return_value = [
        _make_snap(_conv_data())
    ]
    result = list_conversations("uid_abc")
    assert len(result) == 1
    assert result[0].id == "conv_001"


def test_list_empty_returns_empty_list(mock_db: MagicMock) -> None:
    mock_db.collection.return_value.where.return_value.stream.return_value = []
    assert list_conversations("uid_abc") == []


def test_list_sorted_last_message_at_desc(mock_db: MagicMock) -> None:
    earlier = _T0
    later = _T0 + timedelta(hours=1)
    snap_older = _make_snap(_conv_data(id="old", last_message_at=earlier))
    snap_newer = _make_snap(_conv_data(id="new", last_message_at=later))
    mock_db.collection.return_value.where.return_value.stream.return_value = [
        snap_older, snap_newer
    ]
    result = list_conversations("uid_abc")
    assert result[0].id == "new"
    assert result[1].id == "old"


def test_list_nulls_last_in_sort(mock_db: MagicMock) -> None:
    snap_with_msg = _make_snap(_conv_data(id="has_msg", last_message_at=_T0))
    snap_no_msg = _make_snap(_conv_data(id="no_msg", last_message_at=None))
    mock_db.collection.return_value.where.return_value.stream.return_value = [
        snap_no_msg, snap_with_msg
    ]
    result = list_conversations("uid_abc")
    assert result[0].id == "has_msg"
    assert result[1].id == "no_msg"


def test_list_respects_limit(mock_db: MagicMock) -> None:
    snaps = [_make_snap(_conv_data(id=f"conv_{i}")) for i in range(5)]
    mock_db.collection.return_value.where.return_value.stream.return_value = snaps
    result = list_conversations("uid_abc", limit=3)
    assert len(result) == 3


# ---------------------------------------------------------------------------
# delete_conversation
# ---------------------------------------------------------------------------

def test_delete_removes_conversation(mock_db: MagicMock) -> None:
    ref = _make_conv_ref(mock_db, exists=True, data=_conv_data())
    ref.collection.return_value.limit.return_value.stream.return_value = []
    delete_conversation("conv_001", "uid_abc")
    ref.delete.assert_called_once()


def test_delete_not_found_raises_404(mock_db: MagicMock) -> None:
    _make_conv_ref(mock_db, exists=False)
    with pytest.raises(HTTPException) as exc:
        delete_conversation("missing", "uid_abc")
    assert exc.value.status_code == 404


def test_delete_wrong_owner_raises_404(mock_db: MagicMock) -> None:
    ref = _make_conv_ref(mock_db, exists=True, data=_conv_data(owner_uid="uid_abc"))
    with pytest.raises(HTTPException) as exc:
        delete_conversation("conv_001", "uid_attacker")
    assert exc.value.status_code == 404
    ref.delete.assert_not_called()


def test_delete_batch_deletes_messages_before_conversation(mock_db: MagicMock) -> None:
    ref = _make_conv_ref(mock_db, exists=True, data=_conv_data())
    msg_snap = MagicMock()
    msg_snap.reference = MagicMock()
    ref.collection.return_value.limit.return_value.stream.side_effect = [
        [msg_snap],
        [],
    ]
    batch = MagicMock()
    mock_db.batch.return_value = batch

    delete_conversation("conv_001", "uid_abc")

    batch.delete.assert_called_once_with(msg_snap.reference)
    batch.commit.assert_called_once()
    ref.delete.assert_called_once()


# ---------------------------------------------------------------------------
# create_message
# ---------------------------------------------------------------------------

def test_create_message_returns_message(mock_db: MagicMock) -> None:
    ref = _make_conv_ref(mock_db, exists=True, data=_conv_data())
    msg_ref = MagicMock()
    msg_ref.id = "msg_new"
    ref.collection.return_value.document.return_value = msg_ref

    result = create_message("conv_001", "uid_abc", "Hello world")

    assert result.id == "msg_new"
    assert result.role == "user"
    assert result.content == "Hello world"


def test_create_message_role_is_user(mock_db: MagicMock) -> None:
    ref = _make_conv_ref(mock_db, exists=True, data=_conv_data())
    msg_ref = MagicMock()
    msg_ref.id = "msg_new"
    ref.collection.return_value.document.return_value = msg_ref

    result = create_message("conv_001", "uid_abc", "Hello")
    assert result.role == "user"


def test_create_message_writes_to_firestore(mock_db: MagicMock) -> None:
    ref = _make_conv_ref(mock_db, exists=True, data=_conv_data())
    msg_ref = MagicMock()
    msg_ref.id = "msg_new"
    ref.collection.return_value.document.return_value = msg_ref

    create_message("conv_001", "uid_abc", "Hello")
    msg_ref.set.assert_called_once()


def test_create_message_updates_last_message_at(mock_db: MagicMock) -> None:
    ref = _make_conv_ref(mock_db, exists=True, data=_conv_data())
    msg_ref = MagicMock()
    msg_ref.id = "msg_new"
    ref.collection.return_value.document.return_value = msg_ref

    create_message("conv_001", "uid_abc", "Hello")

    update_data: dict[str, object] = ref.update.call_args.args[0]
    assert "last_message_at" in update_data
    assert "updated_at" in update_data


def test_create_message_not_found_raises_404(mock_db: MagicMock) -> None:
    _make_conv_ref(mock_db, exists=False)
    with pytest.raises(HTTPException) as exc:
        create_message("missing", "uid_abc", "Hello")
    assert exc.value.status_code == 404


def test_create_message_wrong_owner_raises_404(mock_db: MagicMock) -> None:
    _make_conv_ref(mock_db, exists=True, data=_conv_data(owner_uid="uid_abc"))
    with pytest.raises(HTTPException) as exc:
        create_message("conv_001", "uid_attacker", "Hello")
    assert exc.value.status_code == 404


# ---------------------------------------------------------------------------
# list_messages
# ---------------------------------------------------------------------------

def test_list_messages_returns_messages(mock_db: MagicMock) -> None:
    ref = _make_conv_ref(mock_db, exists=True, data=_conv_data())
    msg_snap = _make_snap(_msg_data())
    ref.collection.return_value.order_by.return_value.limit.return_value.stream.return_value = [
        msg_snap
    ]
    result = list_messages("conv_001", "uid_abc")
    assert len(result) == 1
    assert result[0].id == "msg_001"


def test_list_messages_empty(mock_db: MagicMock) -> None:
    ref = _make_conv_ref(mock_db, exists=True, data=_conv_data())
    ref.collection.return_value.order_by.return_value.limit.return_value.stream.return_value = []
    result = list_messages("conv_001", "uid_abc")
    assert result == []


def test_list_messages_not_found_raises_404(mock_db: MagicMock) -> None:
    _make_conv_ref(mock_db, exists=False)
    with pytest.raises(HTTPException) as exc:
        list_messages("missing", "uid_abc")
    assert exc.value.status_code == 404


def test_list_messages_wrong_owner_raises_404(mock_db: MagicMock) -> None:
    _make_conv_ref(mock_db, exists=True, data=_conv_data(owner_uid="uid_abc"))
    with pytest.raises(HTTPException) as exc:
        list_messages("conv_001", "uid_attacker")
    assert exc.value.status_code == 404


def test_list_messages_orders_by_created_at(mock_db: MagicMock) -> None:
    ref = _make_conv_ref(mock_db, exists=True, data=_conv_data())
    ref.collection.return_value.order_by.return_value.limit.return_value.stream.return_value = []
    list_messages("conv_001", "uid_abc")
    ref.collection.return_value.order_by.assert_called_once_with("created_at")


def test_list_messages_respects_limit(mock_db: MagicMock) -> None:
    ref = _make_conv_ref(mock_db, exists=True, data=_conv_data())
    ref.collection.return_value.order_by.return_value.limit.return_value.stream.return_value = []
    list_messages("conv_001", "uid_abc", limit=10)
    ref.collection.return_value.order_by.return_value.limit.assert_called_once_with(10)
