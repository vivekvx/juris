"""Google Cloud Speech-to-Text v2 and Text-to-Speech wrappers."""
from __future__ import annotations

import logging
from dataclasses import dataclass

from google.cloud import texttospeech
from google.cloud.speech_v2 import SpeechAsyncClient
from google.cloud.speech_v2.types import cloud_speech

from app.config.settings import get_settings

_log = logging.getLogger(__name__)


@dataclass(frozen=True)
class Transcript:
    text: str
    language: str
    duration_ms: int
    confidence: float


class VoiceProviderError(Exception):
    """STT provider returned an error or is unreachable."""


class NoSpeechDetectedError(Exception):
    """Provider returned a response with no usable transcript."""


class TtsProviderError(Exception):
    """TTS provider returned an error or is unreachable."""


def _get_stt_client() -> SpeechAsyncClient:
    return SpeechAsyncClient()


def _get_tts_client() -> texttospeech.TextToSpeechAsyncClient:
    return texttospeech.TextToSpeechAsyncClient()


async def transcribe(
    audio: bytes,
    mime_type: str,
    language: str | None,
) -> Transcript:
    """Send audio bytes to Cloud Speech-to-Text v2; return typed transcript."""
    settings = get_settings()
    client = _get_stt_client()

    lang_codes: list[str] = [language] if language else ["en-IN", "hi-IN"]
    config = cloud_speech.RecognitionConfig(
        auto_decoding_config=cloud_speech.AutoDetectDecodingConfig(),
        language_codes=lang_codes,
        model=settings.stt_model,
    )
    recognizer = (
        f"projects/{settings.firebase_project_id}/locations/global/recognizers/_"
    )
    request = cloud_speech.RecognizeRequest(
        recognizer=recognizer,
        config=config,
        content=audio,
    )

    try:
        response = await client.recognize(request=request)
    except Exception as exc:
        _log.error("STT provider error: %s", exc)
        raise VoiceProviderError(
            "Speech-to-text service is temporarily unavailable."
        ) from exc

    if not response.results:
        raise NoSpeechDetectedError("No speech detected in the audio.")

    result = response.results[0]
    if not result.alternatives:
        raise NoSpeechDetectedError("No speech detected in the audio.")

    alt = result.alternatives[0]
    end = result.result_end_offset
    duration_ms = int(end.seconds * 1000 + end.nanos // 1_000_000)
    detected_lang: str = result.language_code or (language or "en-IN")

    return Transcript(
        text=alt.transcript,
        language=detected_lang,
        duration_ms=duration_ms,
        confidence=float(alt.confidence),
    )


async def synthesize(text: str, voice: str, language: str) -> bytes:
    """Send text to Cloud Text-to-Speech; return MP3 audio bytes."""
    client = _get_tts_client()
    request = texttospeech.SynthesizeSpeechRequest(
        input=texttospeech.SynthesisInput(text=text),
        voice=texttospeech.VoiceSelectionParams(language_code=language, name=voice),
        audio_config=texttospeech.AudioConfig(
            audio_encoding=texttospeech.AudioEncoding.MP3,
        ),
    )
    try:
        response = await client.synthesize_speech(request=request)
    except Exception as exc:
        _log.error("TTS provider error: %s", exc)
        raise TtsProviderError("Text-to-speech service is temporarily unavailable.") from exc
    audio: bytes = response.audio_content
    return audio
