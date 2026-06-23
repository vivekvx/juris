"""Tests for users service — Firestore mocked, no network calls."""
from __future__ import annotations

from collections.abc import Generator
from datetime import datetime, timezone
from unittest.mock import MagicMock, patch

import pytest

from app.models.user import User
from app.services.users import create_user_if_missing, get_user, upsert_user

_T0 = datetime(2024, 1, 1, 0, 0, 0, tzinfo=timezone.utc)

_STORED: dict[str, object] = {
    "uid": "u1",
    "email": "a@b.com",
    "display_name": "Alice",
    "photo_url": "https://example.com/pic.jpg",
    "preferred_language": "hi",
    "created_at": _T0,
    "updated_at": _T0,
}

_AUTH_USER = User(uid="u1", email="a@b.com", display_name="Alice Updated", photo_url=None)


@pytest.fixture
def mock_db() -> Generator[MagicMock, None, None]:
    with patch("app.services.users.get_firestore_client") as mock_get:
        mock_client = MagicMock()
        mock_get.return_value = mock_client
        yield mock_client


def _make_ref(mock_db: MagicMock, exists: bool, data: dict[str, object] | None = None) -> MagicMock:
    snap = MagicMock()
    snap.exists = exists
    snap.to_dict.return_value = data if exists else None
    ref = MagicMock()
    ref.get.return_value = snap
    mock_db.collection.return_value.document.return_value = ref
    return ref


# ---------------------------------------------------------------------------
# get_user
# ---------------------------------------------------------------------------

def test_get_user_returns_document_when_exists(mock_db: MagicMock) -> None:
    _make_ref(mock_db, exists=True, data=dict(_STORED))
    result = get_user("u1")
    assert result is not None
    assert result.uid == "u1"
    assert result.email == "a@b.com"
    assert result.preferred_language == "hi"


def test_get_user_returns_none_when_missing(mock_db: MagicMock) -> None:
    _make_ref(mock_db, exists=False)
    assert get_user("u1") is None


# ---------------------------------------------------------------------------
# create_user_if_missing
# ---------------------------------------------------------------------------

def test_create_user_if_missing_first_login(mock_db: MagicMock) -> None:
    ref = _make_ref(mock_db, exists=False)
    user = User(uid="u2", email="b@c.com", display_name="Bob", photo_url=None)
    result = create_user_if_missing(user)
    assert result.uid == "u2"
    assert result.email == "b@c.com"
    assert result.preferred_language == "en"
    assert result.created_at == result.updated_at
    ref.set.assert_called_once()


def test_create_user_if_missing_repeated_login_no_write(mock_db: MagicMock) -> None:
    ref = _make_ref(mock_db, exists=True, data=dict(_STORED))
    result = create_user_if_missing(_AUTH_USER)
    assert result.uid == "u1"
    assert result.created_at == _T0
    ref.set.assert_not_called()
    ref.update.assert_not_called()


def test_create_user_if_missing_preserves_existing_fields(mock_db: MagicMock) -> None:
    _make_ref(mock_db, exists=True, data=dict(_STORED))
    result = create_user_if_missing(_AUTH_USER)
    assert result.display_name == "Alice"
    assert result.preferred_language == "hi"


def test_create_user_if_missing_sets_default_language(mock_db: MagicMock) -> None:
    _make_ref(mock_db, exists=False)
    user = User(uid="u3", email=None, display_name=None, photo_url=None)
    result = create_user_if_missing(user)
    assert result.preferred_language == "en"


# ---------------------------------------------------------------------------
# upsert_user
# ---------------------------------------------------------------------------

def test_upsert_user_updates_mutable_fields(mock_db: MagicMock) -> None:
    ref = _make_ref(mock_db, exists=True, data=dict(_STORED))
    result = upsert_user(_AUTH_USER)
    assert result.display_name == "Alice Updated"
    assert result.photo_url is None
    ref.update.assert_called_once()


def test_upsert_user_preserves_created_at(mock_db: MagicMock) -> None:
    _make_ref(mock_db, exists=True, data=dict(_STORED))
    result = upsert_user(_AUTH_USER)
    assert result.created_at == _T0


def test_upsert_user_preserves_preferred_language(mock_db: MagicMock) -> None:
    _make_ref(mock_db, exists=True, data=dict(_STORED))
    result = upsert_user(_AUTH_USER)
    assert result.preferred_language == "hi"


def test_upsert_user_preserves_email(mock_db: MagicMock) -> None:
    _make_ref(mock_db, exists=True, data=dict(_STORED))
    changed = User(uid="u1", email="new@email.com", display_name="Alice", photo_url=None)
    result = upsert_user(changed)
    assert result.email == "a@b.com"


def test_upsert_user_updated_at_is_newer_than_stored(mock_db: MagicMock) -> None:
    _make_ref(mock_db, exists=True, data=dict(_STORED))
    result = upsert_user(_AUTH_USER)
    assert result.updated_at > _T0


def test_upsert_user_calls_update_not_set_on_existing(mock_db: MagicMock) -> None:
    ref = _make_ref(mock_db, exists=True, data=dict(_STORED))
    upsert_user(_AUTH_USER)
    ref.set.assert_not_called()
    ref.update.assert_called_once()


def test_upsert_user_creates_on_first_call(mock_db: MagicMock) -> None:
    ref = _make_ref(mock_db, exists=False)
    user = User(uid="u4", email="d@e.com", display_name="Dave", photo_url=None)
    result = upsert_user(user)
    assert result.uid == "u4"
    assert result.preferred_language == "en"
    ref.set.assert_called_once()
    ref.update.assert_not_called()


# ---------------------------------------------------------------------------
# Timestamp consistency
# ---------------------------------------------------------------------------

def test_created_at_equals_updated_at_on_creation(mock_db: MagicMock) -> None:
    _make_ref(mock_db, exists=False)
    user = User(uid="u5", email=None, display_name=None, photo_url=None)
    result = create_user_if_missing(user)
    assert result.created_at == result.updated_at


def test_created_at_never_changes_across_upserts(mock_db: MagicMock) -> None:
    _make_ref(mock_db, exists=True, data=dict(_STORED))
    result = upsert_user(_AUTH_USER)
    assert result.created_at == _T0
