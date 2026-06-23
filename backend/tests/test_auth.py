"""Tests for backend Firebase token verification and user dependency."""
from collections.abc import Generator
from unittest.mock import MagicMock, patch

import pytest
from fastapi import Depends
from fastapi.testclient import TestClient

from app.core.auth import get_current_user, verify_firebase_token
from app.main import create_app
from app.models.user import User

# ---------------------------------------------------------------------------
# Test app with a single protected route
# ---------------------------------------------------------------------------

_app = create_app()


@_app.get("/protected")
def protected_route(user: User = Depends(get_current_user)) -> dict[str, str | None]:
    return {"uid": user.uid, "email": user.email}


@pytest.fixture
def client() -> TestClient:
    return TestClient(_app, raise_server_exceptions=False)


# Decoded token returned by a successful verify_id_token call
_VALID_CLAIMS: dict[str, object] = {
    "uid": "user-123",
    "email": "test@example.com",
    "name": "Test User",
    "picture": "https://example.com/photo.jpg",
}


@pytest.fixture(autouse=True)
def mock_firebase() -> Generator[MagicMock, None, None]:
    """Patch Firebase Admin so no network calls are made."""
    with patch("app.core.auth.get_firebase_app", return_value=MagicMock()):
        with patch("app.core.auth.firebase_admin.auth.verify_id_token") as mock_verify:
            mock_verify.return_value = _VALID_CLAIMS
            yield mock_verify


# ---------------------------------------------------------------------------
# Missing / malformed header — all must return 401
# ---------------------------------------------------------------------------

def test_missing_auth_header_returns_401(client: TestClient) -> None:
    resp = client.get("/protected")
    assert resp.status_code == 401
    assert "required" in resp.json()["detail"].lower()


def test_malformed_header_not_bearer_returns_401(client: TestClient) -> None:
    resp = client.get("/protected", headers={"Authorization": "Basic dXNlcjpwYXNz"})
    assert resp.status_code == 401


def test_empty_bearer_token_returns_401(client: TestClient) -> None:
    resp = client.get("/protected", headers={"Authorization": "Bearer "})
    assert resp.status_code == 401


# ---------------------------------------------------------------------------
# Token verification failures — all must return 401
# ---------------------------------------------------------------------------

def test_invalid_token_returns_401(
    client: TestClient, mock_firebase: MagicMock
) -> None:
    import firebase_admin.auth as fb_auth  # type: ignore[import-untyped]

    mock_firebase.side_effect = fb_auth.InvalidIdTokenError("bad token")
    resp = client.get("/protected", headers={"Authorization": "Bearer bad-token"})
    assert resp.status_code == 401
    assert resp.json()["detail"] == "Token is invalid."


def test_expired_token_returns_401(
    client: TestClient, mock_firebase: MagicMock
) -> None:
    import firebase_admin.auth as fb_auth  # type: ignore[import-untyped]

    mock_firebase.side_effect = fb_auth.ExpiredIdTokenError("expired", None)
    resp = client.get("/protected", headers={"Authorization": "Bearer expired-token"})
    assert resp.status_code == 401
    assert resp.json()["detail"] == "Token has expired."


def test_revoked_token_returns_401(
    client: TestClient, mock_firebase: MagicMock
) -> None:
    import firebase_admin.auth as fb_auth  # type: ignore[import-untyped]

    mock_firebase.side_effect = fb_auth.RevokedIdTokenError("revoked")
    resp = client.get("/protected", headers={"Authorization": "Bearer revoked-token"})
    assert resp.status_code == 401
    assert resp.json()["detail"] == "Token has been revoked."


def test_unexpected_exception_returns_401(
    client: TestClient, mock_firebase: MagicMock
) -> None:
    mock_firebase.side_effect = RuntimeError("unexpected")
    resp = client.get("/protected", headers={"Authorization": "Bearer some-token"})
    assert resp.status_code == 401
    assert resp.json()["detail"] == "Authentication failed."


# ---------------------------------------------------------------------------
# Valid token — user mapping
# ---------------------------------------------------------------------------

def test_valid_token_returns_200(client: TestClient) -> None:
    resp = client.get("/protected", headers={"Authorization": "Bearer valid-token"})
    assert resp.status_code == 200


def test_user_uid_mapped_from_claims(client: TestClient) -> None:
    resp = client.get("/protected", headers={"Authorization": "Bearer valid-token"})
    assert resp.json()["uid"] == "user-123"


def test_user_email_mapped_from_claims(client: TestClient) -> None:
    resp = client.get("/protected", headers={"Authorization": "Bearer valid-token"})
    assert resp.json()["email"] == "test@example.com"


def test_user_model_fields(mock_firebase: MagicMock) -> None:
    """Unit test: get_current_user maps all claims to User correctly."""
    claims: dict[str, object] = {
        "uid": "u1",
        "email": "a@b.com",
        "name": "Alice",
        "picture": "https://example.com/pic.jpg",
    }
    user = get_current_user(claims)
    assert user.uid == "u1"
    assert user.email == "a@b.com"
    assert user.display_name == "Alice"
    assert user.photo_url == "https://example.com/pic.jpg"


def test_user_optional_fields_default_to_none(mock_firebase: MagicMock) -> None:
    """Claims without email/name/picture produce None fields, not errors."""
    user = get_current_user({"uid": "u2"})
    assert user.email is None
    assert user.display_name is None
    assert user.photo_url is None


def test_error_detail_does_not_leak_token(
    client: TestClient, mock_firebase: MagicMock
) -> None:
    import firebase_admin.auth as fb_auth  # type: ignore[import-untyped]

    mock_firebase.side_effect = fb_auth.InvalidIdTokenError("secret-internal-details")
    resp = client.get("/protected", headers={"Authorization": "Bearer secret-token"})
    body = resp.text
    assert "secret-internal-details" not in body
    assert "secret-token" not in body
