"""Unit tests for app.services.voice — Cloud STT and TTS clients mocked."""
from __future__ import annotations

from collections.abc import Generator
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from app.services.voice import (
    NoSpeechDetectedError,
    Transcript,
    TtsProviderError,
    VoiceProviderError,
    synthesize,
    transcribe,
)

_WEBM_BYTES = b"\x1a\x45\xdf\xa3" + b"\x00" * 100


def _make_stt_response(
    transcript_text: str,
    language: str,
    seconds: int,
    nanos: int,
    confidence: float,
) -> MagicMock:
    alt = MagicMock()
    alt.transcript = transcript_text
    alt.confidence = confidence

    end = MagicMock()
    end.seconds = seconds
    end.nanos = nanos

    result = MagicMock()
    result.alternatives = [alt]
    result.result_end_offset = end
    result.language_code = language

    response = MagicMock()
    response.results = [result]
    return response


@pytest.fixture(autouse=True)
def _mock_settings() -> Generator[None, None, None]:
    with patch("app.services.voice.get_settings") as mock:
        s = MagicMock()
        s.stt_model = "latest_long"
        s.firebase_project_id = "test-project"
        mock.return_value = s
        yield


async def test_transcribe_returns_typed_transcript() -> None:
    resp = _make_stt_response("What are my rights?", "en-IN", 3, 500_000_000, 0.95)
    mock_client = AsyncMock()
    mock_client.recognize = AsyncMock(return_value=resp)

    with patch("app.services.voice._get_stt_client", return_value=mock_client):
        result = await transcribe(_WEBM_BYTES, "audio/webm", None)

    assert isinstance(result, Transcript)
    assert result.text == "What are my rights?"
    assert result.language == "en-IN"
    assert result.duration_ms == 3500  # 3s + 500ms
    assert result.confidence == pytest.approx(0.95)


async def test_transcribe_with_language_hint_passes_lang() -> None:
    resp = _make_stt_response("नमस्ते", "hi-IN", 2, 0, 0.90)
    mock_client = AsyncMock()
    mock_client.recognize = AsyncMock(return_value=resp)

    with patch("app.services.voice._get_stt_client", return_value=mock_client):
        result = await transcribe(_WEBM_BYTES, "audio/webm", "hi-IN")

    assert result.language == "hi-IN"
    assert result.text == "नमस्ते"
    assert result.duration_ms == 2000


async def test_transcribe_empty_results_raises_no_speech() -> None:
    resp = MagicMock()
    resp.results = []
    mock_client = AsyncMock()
    mock_client.recognize = AsyncMock(return_value=resp)

    with patch("app.services.voice._get_stt_client", return_value=mock_client):
        with pytest.raises(NoSpeechDetectedError):
            await transcribe(_WEBM_BYTES, "audio/webm", None)


async def test_transcribe_empty_alternatives_raises_no_speech() -> None:
    result = MagicMock()
    result.alternatives = []
    result.language_code = "en-IN"
    resp = MagicMock()
    resp.results = [result]
    mock_client = AsyncMock()
    mock_client.recognize = AsyncMock(return_value=resp)

    with patch("app.services.voice._get_stt_client", return_value=mock_client):
        with pytest.raises(NoSpeechDetectedError):
            await transcribe(_WEBM_BYTES, "audio/webm", None)


async def test_transcribe_provider_exception_wraps_as_voice_error() -> None:
    mock_client = AsyncMock()
    mock_client.recognize = AsyncMock(side_effect=RuntimeError("gRPC deadline exceeded"))

    with patch("app.services.voice._get_stt_client", return_value=mock_client):
        with pytest.raises(VoiceProviderError):
            await transcribe(_WEBM_BYTES, "audio/webm", None)


# ===========================================================================
# synthesize — TTS
# ===========================================================================

_FAKE_MP3 = b"ID3" + b"\x00" * 64


def _make_tts_response(audio: bytes) -> MagicMock:
    resp = MagicMock()
    resp.audio_content = audio
    return resp


async def test_synthesize_returns_mp3_bytes() -> None:
    mock_client = AsyncMock()
    mock_client.synthesize_speech = AsyncMock(return_value=_make_tts_response(_FAKE_MP3))

    with patch("app.services.voice._get_tts_client", return_value=mock_client):
        result = await synthesize("Hello world", "en-IN-Neural2-A", "en-IN")

    assert result == _FAKE_MP3
    mock_client.synthesize_speech.assert_awaited_once()


async def test_synthesize_passes_voice_and_language() -> None:
    mock_client = AsyncMock()
    mock_client.synthesize_speech = AsyncMock(return_value=_make_tts_response(_FAKE_MP3))

    with patch("app.services.voice._get_tts_client", return_value=mock_client):
        await synthesize("नमस्ते", "hi-IN-Neural2-A", "hi-IN")

    call_kwargs = mock_client.synthesize_speech.call_args
    request = call_kwargs.kwargs.get("request") or call_kwargs.args[0]
    assert request.voice.name == "hi-IN-Neural2-A"
    assert request.voice.language_code == "hi-IN"
    assert request.input.text == "नमस्ते"


async def test_synthesize_provider_exception_wraps_as_tts_error() -> None:
    mock_client = AsyncMock()
    mock_client.synthesize_speech = AsyncMock(side_effect=RuntimeError("quota exceeded"))

    with patch("app.services.voice._get_tts_client", return_value=mock_client):
        with pytest.raises(TtsProviderError):
            await synthesize("Hello", "en-IN-Neural2-A", "en-IN")
