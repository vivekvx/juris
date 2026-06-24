"""Voice API: POST /api/voice/transcribe.

Stateless endpoint — no Firestore, no GCS, no conversation state touched.
Audio bytes are transcribed in-memory and discarded.
"""
from __future__ import annotations

import logging

from fastapi import APIRouter, Depends, Form, HTTPException, UploadFile, status
from pydantic import BaseModel

from app.config.settings import get_settings
from app.core.auth import get_current_user
from app.models.user import User
from app.services.voice import NoSpeechDetectedError, VoiceProviderError, transcribe

_log = logging.getLogger(__name__)

router = APIRouter(prefix="/api/voice", tags=["voice"])

_ALLOWED_MIME_TYPES: frozenset[str] = frozenset({
    "audio/webm",
    "audio/ogg",
    "audio/mp4",
    "audio/wav",
    "audio/mpeg",
})

# (magic_prefix, canonical_mime)
_MAGIC_SIGNATURES: list[tuple[bytes, str]] = [
    (b"OggS", "audio/ogg"),
    (b"\x1a\x45\xdf\xa3", "audio/webm"),
    (b"RIFF", "audio/wav"),
    (b"ID3", "audio/mpeg"),
    (b"\xff\xfb", "audio/mpeg"),
    (b"\xff\xf3", "audio/mpeg"),
    (b"\xff\xf2", "audio/mpeg"),
]


def _sniff_mime(data: bytes) -> str | None:
    """Return MIME type from leading magic bytes, or None if unrecognized."""
    for magic, mime in _MAGIC_SIGNATURES:
        if data[: len(magic)] == magic:
            return mime
    # MP4/AAC: 'ftyp' box at byte offset 4
    if len(data) >= 8 and data[4:8] == b"ftyp":
        return "audio/mp4"
    return None


class TranscribeResponse(BaseModel):
    text: str
    language: str
    duration_ms: int
    confidence: float


@router.post("/transcribe", response_model=TranscribeResponse)
async def transcribe_audio(
    file: UploadFile,
    language: str | None = Form(default=None),
    current_user: User = Depends(get_current_user),
) -> TranscribeResponse:
    settings = get_settings()
    data = await file.read()

    if not data:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Audio file is empty.",
        )

    if len(data) > settings.voice_max_audio_bytes:
        raise HTTPException(
            status_code=413,
            detail=(
                f"Audio size {len(data):,} bytes exceeds the "
                f"{settings.voice_max_audio_bytes // (1024 * 1024)} MB limit."
            ),
        )

    declared_mime = (file.content_type or "").split(";")[0].strip()
    sniffed_mime = _sniff_mime(data)
    effective_mime = sniffed_mime or declared_mime

    if effective_mime not in _ALLOWED_MIME_TYPES:
        raise HTTPException(
            status_code=status.HTTP_415_UNSUPPORTED_MEDIA_TYPE,
            detail=(
                f"Audio format {effective_mime!r} is not supported. "
                "Accepted: audio/webm, audio/ogg, audio/mp4, audio/wav, audio/mpeg."
            ),
        )

    try:
        result = await transcribe(data, effective_mime, language)
    except NoSpeechDetectedError:
        raise HTTPException(
            status_code=422,
            detail="No speech detected. Please try again.",
        )
    except VoiceProviderError:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="Transcription unavailable. Please type instead.",
        )

    return TranscribeResponse(
        text=result.text,
        language=result.language,
        duration_ms=result.duration_ms,
        confidence=result.confidence,
    )
