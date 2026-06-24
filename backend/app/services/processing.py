"""Document processing background task.

Pipeline: GCS read → MarkItDown → chunk → embed → Firestore write → READY.
Runs as a FastAPI BackgroundTask after the upload response is sent.

Cloud Run note: requires min-instances=1 to prevent instance termination
mid-processing. Documents stuck in PROCESSING for >10 minutes are recovered
by the startup check in main.py (recover_stuck_documents).
"""
from __future__ import annotations

import io
import logging
import uuid
from datetime import datetime, timezone

from markitdown import MarkItDown, StreamInfo

from app.config.settings import get_settings
from app.core.firebase import get_storage_bucket
from app.models.chunk import Chunk, CURRENT_CHUNK_VERSION, EMBEDDING_MODEL
from app.models.document import DocumentStatus
from app.repositories.chunk_repo import delete_chunks, write_chunks
from app.services.chunking import chunk_document
from app.services.documents import (
    get_document,
    update_document_status,
    update_indexed,
)
from app.services.embedding import embed_chunks

_log = logging.getLogger(__name__)
_MIME_TO_EXT: dict[str, str] = {
    "application/pdf": ".pdf",
    "application/vnd.openxmlformats-officedocument.wordprocessingml.document": ".docx",
    "text/plain": ".txt",
}


def _utc_now() -> datetime:
    return datetime.now(tz=timezone.utc)


def _read_from_gcs(storage_path: str) -> bytes:
    return bytes(get_storage_bucket().blob(storage_path).download_as_bytes())


def _extract_text(data: bytes, mime_type: str) -> str:
    ext = _MIME_TO_EXT.get(mime_type, "")
    result = MarkItDown().convert_stream(
        io.BytesIO(data),
        stream_info=StreamInfo(mimetype=mime_type, extension=ext),
    )
    return result.text_content or ""


async def process_document(doc_id: str, owner_uid: str) -> None:
    """Full M3 processing pipeline. Called as a FastAPI BackgroundTask."""
    settings = get_settings()
    _log.info("Processing doc %s for user %s", doc_id, owner_uid)

    try:
        doc = get_document(doc_id, owner_uid)
    except Exception as exc:
        _log.error("Cannot load document %s: %s", doc_id, exc)
        return

    if doc.status != DocumentStatus.PROCESSING:
        _log.warning("Doc %s is %s, expected PROCESSING — skipping", doc_id, doc.status)
        return

    # Stage 1: GCS read
    try:
        data = _read_from_gcs(doc.storage_path)
    except Exception as exc:
        _log.error("GCS read failed for doc %s: %s", doc_id, exc)
        update_document_status(
            doc_id, DocumentStatus.FAILED, owner_uid,
            error_message=f"Storage read error: {exc}",
        )
        return

    # Stage 2: MarkItDown extraction
    try:
        text = _extract_text(data, doc.mime_type)
    except Exception as exc:
        _log.error("Text extraction failed for doc %s: %s", doc_id, exc)
        update_document_status(
            doc_id, DocumentStatus.FAILED, owner_uid,
            error_message=f"Text extraction failed: {exc}",
        )
        return

    if not text or len(text.strip()) < 20:
        update_document_status(
            doc_id, DocumentStatus.FAILED, owner_uid,
            error_message="No text content extracted",
        )
        return

    # Stage 3: Chunking
    raw_chunks = chunk_document(
        text,
        mime_type=doc.mime_type,
        size_tokens=settings.chunk_size_tokens,
        overlap_tokens=settings.chunk_overlap_tokens,
        max_chunks=settings.max_chunks_per_document + 1,  # +1 to detect truncation
    )

    if not raw_chunks:
        update_document_status(
            doc_id, DocumentStatus.FAILED, owner_uid,
            error_message="No chunks produced",
        )
        return

    truncated = len(raw_chunks) > settings.max_chunks_per_document
    if truncated:
        raw_chunks = raw_chunks[: settings.max_chunks_per_document]

    # Stage 4: Embedding
    texts = [content for _, content, _ in raw_chunks]
    try:
        vectors = await embed_chunks(texts)
    except Exception as exc:
        _log.error("Embedding failed for doc %s: %s", doc_id, exc)
        update_document_status(
            doc_id, DocumentStatus.FAILED, owner_uid,
            error_message=f"Embedding failed: {exc}",
        )
        return

    # Stage 5: Build Chunk objects
    now = _utc_now()
    chunks: list[Chunk] = [
        Chunk(
            id=str(uuid.uuid4()),
            doc_id=doc_id,
            owner_uid=owner_uid,
            content=content,
            embedding=embedding,
            chunk_index=idx,
            page_number=page_number,
            token_count=token_count,
            chunk_version=CURRENT_CHUNK_VERSION,
            embedding_model=EMBEDDING_MODEL,
            created_at=now,
        )
        for idx, ((page_number, content, token_count), embedding) in enumerate(zip(raw_chunks, vectors))
    ]

    # Stage 6: Write to Firestore (commit gate — READY set only after all chunks written)
    try:
        await write_chunks(doc_id, chunks)
    except Exception as exc:
        _log.error("Chunk write failed for doc %s: %s", doc_id, exc)
        try:
            await delete_chunks(doc_id)
        except Exception as cleanup_exc:
            _log.error("Chunk cleanup also failed for doc %s: %s", doc_id, cleanup_exc)
        update_document_status(
            doc_id, DocumentStatus.FAILED, owner_uid,
            error_message="Chunk storage failed",
        )
        return

    # Stage 7: Mark READY with indexed metadata
    update_indexed(
        doc_id=doc_id,
        owner_uid=owner_uid,
        chunk_count=len(chunks),
        processing_warning="truncated at 1000 chunks" if truncated else None,
    )
    _log.info("Doc %s ready: %d chunks%s", doc_id, len(chunks), " (truncated)" if truncated else "")
