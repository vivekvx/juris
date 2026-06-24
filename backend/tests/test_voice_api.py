"""Tests for POST /api/voice/transcribe — STT provider mocked, no network calls."""
from __future__ import annotations

from collections.abc import Generator
from io import BytesIO
from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from fastapi.testclient import TestClient

from app.core.auth import get_current_user
from app.main import create_app
from app.models.user import User
from app.services.voice import NoSpeechDetectedError, Transcript, VoiceProviderError

_USER = User(uid="uid_test", email="test@example.com", display_name=None, photo_url=None)

# Minimal valid magic-byte prefixes
_WEBM_BYTES = b"\x1a\x45\xdf\xa3" + b"\x00" * 100
_OGG_BYTES = b"OggS" + b"\x00" * 100
_WAV_BYTES = b"RIFF" + b"\x00" * 40 + b"WAVE" + b"\x00" * 56

_TRANSCRIPT = Transcript(
    text="What are my rights under this contract?",
    language="en-IN",
    duration_ms=3500,
    confidence=0.97,
)


@pytest.fixture
def client() -> Generator[TestClient, None, None]:
    app = create_app()
    app.dependency_overrides[get_current_user] = lambda: _USER
    with TestClient(app) as c:
        yield c


def _upload(
    c: TestClient,
    data: bytes,
    content_type: str = "audio/webm",
    language: str | None = None,
) -> object:
    files = {"file": ("audio.webm", BytesIO(data), content_type)}
    form: dict[str, str] = {}
    if language:
        form["language"] = language
    return c.post("/api/voice/transcribe", files=files, data=form)


# ---------------------------------------------------------------------------
# Success paths
# ---------------------------------------------------------------------------

def test_transcribe_webm_returns_200(client: TestClient) -> None:
    with patch("app.api.voice.transcribe", new=AsyncMock(return_value=_TRANSCRIPT)):
        resp = _upload(client, _WEBM_BYTES)
    assert resp.status_code == 200
    body = resp.json()
    assert body["text"] == _TRANSCRIPT.text
    assert body["language"] == "en-IN"
    assert body["duration_ms"] == 3500
    assert body["confidence"] == pytest.approx(0.97)


def test_transcribe_ogg_accepted(client: TestClient) -> None:
    with patch("app.api.voice.transcribe", new=AsyncMock(return_value=_TRANSCRIPT)):
        resp = _upload(client, _OGG_BYTES, content_type="audio/ogg")
    assert resp.status_code == 200


def test_transcribe_wav_accepted(client: TestClient) -> None:
    with patch("app.api.voice.transcribe", new=AsyncMock(return_value=_TRANSCRIPT)):
        resp = _upload(client, _WAV_BYTES, content_type="audio/wav")
    assert resp.status_code == 200


def test_transcribe_with_language_hint(client: TestClient) -> None:
    with patch("app.api.voice.transcribe", new=AsyncMock(return_value=_TRANSCRIPT)):
        resp = _upload(client, _WEBM_BYTES, language="hi-IN")
    assert resp.status_code == 200


# ---------------------------------------------------------------------------
# Auth
# ---------------------------------------------------------------------------

def test_transcribe_requires_auth() -> None:
    app = create_app()  # no dependency override
    with TestClient(app) as anon:
        resp = _upload(anon, _WEBM_BYTES)
    assert resp.status_code == 401


# ---------------------------------------------------------------------------
# Validation errors
# ---------------------------------------------------------------------------

def test_transcribe_empty_file_returns_400(client: TestClient) -> None:
    resp = _upload(client, b"")
    assert resp.status_code == 400


def test_transcribe_unsupported_mime_returns_415(client: TestClient) -> None:
    # Fake PDF bytes — sniff returns None; declared type is application/pdf
    resp = _upload(client, b"%PDF-1.4 fake pdf", content_type="application/pdf")
    assert resp.status_code == 415


def test_transcribe_file_too_large_returns_413(client: TestClient) -> None:
    # Patch settings to a small limit so the test doesn't allocate 10 MB
    settings_mock = MagicMock()
    settings_mock.voice_max_audio_bytes = 50
    settings_mock.stt_model = "latest_long"
    settings_mock.firebase_project_id = "test-project"
    with patch("app.api.voice.get_settings", return_value=settings_mock):
        resp = _upload(client, _WEBM_BYTES)  # 104 bytes > 50
    assert resp.status_code == 413


# ---------------------------------------------------------------------------
# Provider error paths
# ---------------------------------------------------------------------------

def test_transcribe_no_speech_returns_422(client: TestClient) -> None:
    with patch(
        "app.api.voice.transcribe",
        new=AsyncMock(side_effect=NoSpeechDetectedError("no speech")),
    ):
        resp = _upload(client, _WEBM_BYTES)
    assert resp.status_code == 422
    assert "No speech" in resp.json()["detail"]


def test_transcribe_provider_error_returns_503(client: TestClient) -> None:
    with patch(
        "app.api.voice.transcribe",
        new=AsyncMock(side_effect=VoiceProviderError("timeout")),
    ):
        resp = _upload(client, _WEBM_BYTES)
    assert resp.status_code == 503
    assert "unavailable" in resp.json()["detail"].lower()
