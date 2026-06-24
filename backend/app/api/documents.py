"""Document upload API.

Routes orchestrate services only — no Firestore, no GCS, no Firebase here.
"""
from __future__ import annotations

import uuid
from datetime import datetime, timezone

from fastapi import APIRouter, BackgroundTasks, Depends, HTTPException, UploadFile, status
from pydantic import BaseModel

from app.core.auth import get_current_user
from app.models.document import Document, DocumentStatus
from app.models.user import User
from app.services.documents import (
    create_document,
    delete_document,
    get_document,
    list_documents,
    mark_processing,
    update_document_status,
)
from app.services.processing import process_document
from app.services.storage import delete_file, generate_storage_path, upload_file

router = APIRouter(prefix="/api/documents", tags=["documents"])

_ALLOWED_MIME_TYPES: frozenset[str] = frozenset({
    "application/pdf",
    "application/vnd.openxmlformats-officedocument.wordprocessingml.document",
    "text/plain",
})
_MAX_SIZE_BYTES: int = 20 * 1024 * 1024  # 20 MB


class DocumentResponse(BaseModel):
    id: str
    filename: str
    original_filename: str
    mime_type: str
    size_bytes: int
    status: DocumentStatus
    error_message: str | None
    indexed_at: str | None
    chunk_count: int | None
    processing_warning: str | None
    created_at: str
    updated_at: str


def _sanitize_filename(name: str) -> str:
    sanitized = "".join(
        c if c.isascii() and (c.isalnum() or c in ".-_") else "_"
        for c in name
    )
    return sanitized[:200] or "file"


def _to_response(doc: Document) -> DocumentResponse:
    data = doc.model_dump(mode="json")
    return DocumentResponse(
        id=data["id"],
        filename=data["filename"],
        original_filename=data["original_filename"],
        mime_type=data["mime_type"],
        size_bytes=data["size_bytes"],
        status=doc.status,
        error_message=data["error_message"],
        indexed_at=data["indexed_at"],
        chunk_count=data["chunk_count"],
        processing_warning=data["processing_warning"],
        created_at=data["created_at"],
        updated_at=data["updated_at"],
    )


@router.post(
    "/",
    response_model=DocumentResponse,
    status_code=status.HTTP_201_CREATED,
)
async def upload_document(
    file: UploadFile,
    background_tasks: BackgroundTasks,
    current_user: User = Depends(get_current_user),
) -> DocumentResponse:
    mime_type = file.content_type or ""
    if mime_type not in _ALLOWED_MIME_TYPES:
        raise HTTPException(
            status_code=status.HTTP_415_UNSUPPORTED_MEDIA_TYPE,
            detail=(
                f"File type {mime_type!r} is not supported. "
                "Accepted: application/pdf, "
                "application/vnd.openxmlformats-officedocument.wordprocessingml.document, "
                "text/plain."
            ),
        )

    data = await file.read()

    if len(data) > _MAX_SIZE_BYTES:
        raise HTTPException(
            status_code=status.HTTP_413_REQUEST_ENTITY_TOO_LARGE,
            detail=f"File size {len(data):,} bytes exceeds the 20 MB limit.",
        )

    now = datetime.now(tz=timezone.utc)
    original_filename = file.filename or "upload"
    filename = _sanitize_filename(original_filename)
    document_id = str(uuid.uuid4())
    storage_path = generate_storage_path(current_user.uid, document_id, filename)

    doc = create_document(
        Document(
            id=document_id,
            owner_uid=current_user.uid,
            filename=filename,
            original_filename=original_filename,
            mime_type=mime_type,
            size_bytes=len(data),
            status=DocumentStatus.UPLOADING,
            storage_path=storage_path,
            created_at=now,
            updated_at=now,
        )
    )

    try:
        upload_file(data, storage_path, mime_type)
    except Exception:
        update_document_status(
            doc.id,
            DocumentStatus.FAILED,
            current_user.uid,
            error_message="Storage write failed.",
        )
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="Failed to store the document. Please try again.",
        )

    doc = mark_processing(doc.id, current_user.uid)
    background_tasks.add_task(process_document, doc.id, current_user.uid)
    return _to_response(doc)


@router.get("/", response_model=list[DocumentResponse])
def list_documents_route(
    current_user: User = Depends(get_current_user),
) -> list[DocumentResponse]:
    docs = list_documents(current_user.uid)
    return [_to_response(d) for d in docs]


@router.get("/{document_id}", response_model=DocumentResponse)
def get_document_route(
    document_id: str,
    current_user: User = Depends(get_current_user),
) -> DocumentResponse:
    doc = get_document(document_id, current_user.uid)
    return _to_response(doc)


@router.delete("/{document_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_document_route(
    document_id: str,
    current_user: User = Depends(get_current_user),
) -> None:
    doc = get_document(document_id, current_user.uid)
    try:
        delete_file(doc.storage_path)
    except Exception:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="Failed to delete file from storage. Please try again.",
        )
    delete_document(document_id, current_user.uid)
