"""Tests for lazy Firebase Admin initialization.

All tests run without real Firebase credentials by patching at the right boundary.
"""
from __future__ import annotations

from unittest.mock import MagicMock, patch

import pytest

import app.core.firebase as firebase_module
from app.core.firebase import (
    get_firebase_app,
    get_firestore_client,
    get_storage_bucket,
    reset_firebase_app,
)


@pytest.fixture(autouse=True)
def _reset_singleton():
    """Ensure each test starts with a clean Firebase singleton."""
    original = firebase_module._app
    firebase_module._app = None
    yield
    firebase_module._app = original


# ---------------------------------------------------------------------------
# Error cases — no credentials
# ---------------------------------------------------------------------------

def test_get_firebase_app_without_creds_raises(monkeypatch):
    monkeypatch.setattr(firebase_module.get_settings(), "firebase_credentials", "")
    with pytest.raises(RuntimeError, match="FIREBASE_CREDENTIALS"):
        get_firebase_app()


def test_get_firestore_client_without_creds_raises(monkeypatch):
    monkeypatch.setattr(firebase_module.get_settings(), "firebase_credentials", "")
    with pytest.raises(RuntimeError, match="FIREBASE_CREDENTIALS"):
        get_firestore_client()


def test_get_storage_bucket_without_creds_raises(monkeypatch):
    monkeypatch.setattr(firebase_module.get_settings(), "firebase_credentials", "")
    with pytest.raises(RuntimeError, match="FIREBASE_CREDENTIALS"):
        get_storage_bucket()


# ---------------------------------------------------------------------------
# Lazy singleton behaviour
# ---------------------------------------------------------------------------

def _mock_settings(monkeypatch) -> None:
    """Point settings at a fake credentials path so _ensure_app() proceeds."""
    s = firebase_module.get_settings()
    monkeypatch.setattr(s, "firebase_credentials", "/fake/creds.json")
    monkeypatch.setattr(s, "firebase_project_id", "test-project")
    monkeypatch.setattr(s, "firebase_storage_bucket", "test-bucket.appspot.com")


def test_initialize_app_called_once(monkeypatch):
    """firebase_admin.initialize_app must be called exactly once across multiple accessors."""
    _mock_settings(monkeypatch)
    mock_app = MagicMock()

    with (
        patch("app.core.firebase.credentials.Certificate"),
        patch("app.core.firebase.firebase_admin.initialize_app", return_value=mock_app) as mock_init,
        patch("app.core.firebase.firestore.client"),
        patch("app.core.firebase.storage.bucket"),
    ):
        get_firebase_app()
        get_firebase_app()  # second call — must not re-initialize
        get_firestore_client()
        get_storage_bucket()
        assert mock_init.call_count == 1


def test_reset_clears_singleton(monkeypatch):
    """reset_firebase_app() must clear the singleton so next call re-initializes."""
    _mock_settings(monkeypatch)
    mock_app = MagicMock()

    with (
        patch("app.core.firebase.credentials.Certificate"),
        patch("app.core.firebase.firebase_admin.initialize_app", return_value=mock_app) as mock_init,
        patch("app.core.firebase.firebase_admin.delete_app"),
    ):
        get_firebase_app()
        reset_firebase_app()
        get_firebase_app()
        assert mock_init.call_count == 2


def test_reset_noop_when_not_initialized():
    """reset_firebase_app() must not raise if called before initialization."""
    reset_firebase_app()  # should not raise


# ---------------------------------------------------------------------------
# Accessor isolation — each accessor calls through to Firebase SDK
# ---------------------------------------------------------------------------

def test_get_firestore_client_calls_sdk(monkeypatch):
    _mock_settings(monkeypatch)
    mock_client = MagicMock()

    with (
        patch("app.core.firebase.credentials.Certificate"),
        patch("app.core.firebase.firebase_admin.initialize_app", return_value=MagicMock()),
        patch("app.core.firebase.firestore.client", return_value=mock_client) as mock_fs,
    ):
        result = get_firestore_client()
        assert mock_fs.called
        assert result is mock_client


def test_get_storage_bucket_calls_sdk(monkeypatch):
    _mock_settings(monkeypatch)
    mock_bucket = MagicMock()

    with (
        patch("app.core.firebase.credentials.Certificate"),
        patch("app.core.firebase.firebase_admin.initialize_app", return_value=MagicMock()),
        patch("app.core.firebase.storage.bucket", return_value=mock_bucket) as mock_st,
    ):
        result = get_storage_bucket()
        assert mock_st.called
        assert result is mock_bucket
