"""Tests for POST /api/users/me — auth mocked via dependency override."""
from __future__ import annotations

from datetime import datetime, timezone
from unittest.mock import patch

import pytest
from fastapi.testclient import TestClient

from app.core.auth import get_current_user
from app.main import create_app
from app.models.user import User, UserDocument

_T0 = datetime(2024, 1, 1, 0, 0, 0, tzinfo=timezone.utc)

_AUTH_USER = User(uid="u1", email="a@b.com", display_name="Alice", photo_url=None)

_EXISTING_DOC = UserDocument(
    uid="u1",
    email="a@b.com",
    display_name="Alice",
    photo_url=None,
    preferred_language="hi",
    created_at=_T0,
    updated_at=_T0,
)

_NEW_DOC = UserDocument(
    uid="u1",
    email="a@b.com",
    display_name="Alice",
    photo_url=None,
    preferred_language="en",
    created_at=_T0,
    updated_at=_T0,
)


@pytest.fixture
def client() -> TestClient:
    app = create_app()
    app.dependency_overrides[get_current_user] = lambda: _AUTH_USER
    return TestClient(app, raise_server_exceptions=False)


@pytest.fixture
def unauthed_client() -> TestClient:
    return TestClient(create_app(), raise_server_exceptions=False)


# ---------------------------------------------------------------------------
# Auth guard
# ---------------------------------------------------------------------------

def test_post_me_requires_auth(unauthed_client: TestClient) -> None:
    resp = unauthed_client.post("/api/users/me")
    assert resp.status_code == 401


# ---------------------------------------------------------------------------
# First login
# ---------------------------------------------------------------------------

def test_post_me_first_login_returns_200(client: TestClient) -> None:
    with patch("app.api.users.create_user_if_missing", return_value=_NEW_DOC):
        resp = client.post("/api/users/me")
    assert resp.status_code == 200


def test_post_me_first_login_creates_profile(client: TestClient) -> None:
    with patch("app.api.users.create_user_if_missing", return_value=_NEW_DOC) as mock_create:
        client.post("/api/users/me")
    mock_create.assert_called_once_with(_AUTH_USER)


def test_post_me_first_login_default_language(client: TestClient) -> None:
    with patch("app.api.users.create_user_if_missing", return_value=_NEW_DOC):
        resp = client.post("/api/users/me")
    assert resp.json()["preferred_language"] == "en"


# ---------------------------------------------------------------------------
# Repeated login — metadata preservation
# ---------------------------------------------------------------------------

def test_post_me_repeated_login_returns_200(client: TestClient) -> None:
    with patch("app.api.users.create_user_if_missing", return_value=_EXISTING_DOC):
        resp = client.post("/api/users/me")
    assert resp.status_code == 200


def test_post_me_repeated_login_preserves_language(client: TestClient) -> None:
    with patch("app.api.users.create_user_if_missing", return_value=_EXISTING_DOC):
        resp = client.post("/api/users/me")
    assert resp.json()["preferred_language"] == "hi"


def test_post_me_repeated_login_calls_service_once(client: TestClient) -> None:
    with patch("app.api.users.create_user_if_missing", return_value=_EXISTING_DOC) as mock_create:
        client.post("/api/users/me")
    mock_create.assert_called_once()


# ---------------------------------------------------------------------------
# Response model shape
# ---------------------------------------------------------------------------

def test_post_me_response_contains_uid(client: TestClient) -> None:
    with patch("app.api.users.create_user_if_missing", return_value=_EXISTING_DOC):
        resp = client.post("/api/users/me")
    assert resp.json()["uid"] == "u1"


def test_post_me_response_contains_email(client: TestClient) -> None:
    with patch("app.api.users.create_user_if_missing", return_value=_EXISTING_DOC):
        resp = client.post("/api/users/me")
    assert resp.json()["email"] == "a@b.com"


def test_post_me_response_does_not_expose_timestamps(client: TestClient) -> None:
    with patch("app.api.users.create_user_if_missing", return_value=_EXISTING_DOC):
        resp = client.post("/api/users/me")
    body = resp.json()
    assert "created_at" not in body
    assert "updated_at" not in body


def test_post_me_response_fields_match_schema(client: TestClient) -> None:
    with patch("app.api.users.create_user_if_missing", return_value=_EXISTING_DOC):
        resp = client.post("/api/users/me")
    body = resp.json()
    assert set(body.keys()) == {"uid", "email", "display_name", "photo_url", "preferred_language"}


# ---------------------------------------------------------------------------
# Failure paths
# ---------------------------------------------------------------------------

def test_post_me_service_exception_returns_500(client: TestClient) -> None:
    with patch("app.api.users.create_user_if_missing", side_effect=RuntimeError("firestore down")):
        resp = client.post("/api/users/me")
    assert resp.status_code == 500


def test_post_me_null_photo_url_serializes_correctly(client: TestClient) -> None:
    with patch("app.api.users.create_user_if_missing", return_value=_EXISTING_DOC):
        resp = client.post("/api/users/me")
    assert resp.json()["photo_url"] is None
