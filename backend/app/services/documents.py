"""Document service layer — Firestore metadata operations only.

No file bytes, no Storage writes, no processing.
All ownership checks live here; route handlers never touch Firestore directly.
"""
from __future__ import annotations

from datetime import datetime, timezone
from typing import Any, cast

from fastapi import HTTPException
from google.cloud.firestore import DocumentSnapshot

from app.core.firebase import get_firestore_client
from app.models.document import Document, DocumentStatus

_COLLECTION = "documents"

# Explicit state machine. Every allowed (from, to) pair is listed.
# Anything not in this set is rejected with 409.
_ALLOWED_TRANSITIONS: frozenset[tuple[DocumentStatus, DocumentStatus]] = frozenset({
    (DocumentStatus.UPLOADING,  DocumentStatus.PROCESSING),
    (DocumentStatus.UPLOADING,  DocumentStatus.FAILED),
    (DocumentStatus.PROCESSING, DocumentStatus.READY),
    (DocumentStatus.PROCESSING, DocumentStatus.FAILED),
})


def _utc_now() -> datetime:
    return datetime.now(tz=timezone.utc)


def _snap_to_doc(snap: DocumentSnapshot) -> Document:
    data = snap.to_dict()
    if data is None:
        raise HTTPException(status_code=404, detail="Document not found.")
    return Document.model_validate(data)


def get_document(document_id: str, owner_uid: str) -> Document:
    ref = get_firestore_client().collection(_COLLECTION).document(document_id)
    snap = cast(DocumentSnapshot, ref.get())
    if not snap.exists:
        raise HTTPException(status_code=404, detail="Document not found.")
    doc = _snap_to_doc(snap)
    if doc.owner_uid != owner_uid:
        raise HTTPException(status_code=403, detail="Access denied.")
    return doc


def list_documents(owner_uid: str) -> list[Document]:
    snaps = (
        get_firestore_client()
        .collection(_COLLECTION)
        .where("owner_uid", "==", owner_uid)
        .stream()
    )
    result: list[Document] = []
    for snap in snaps:
        data = snap.to_dict()
        if data is not None:
            result.append(Document.model_validate(data))
    return sorted(result, key=lambda d: d.updated_at, reverse=True)


def create_document(document: Document) -> Document:
    if document.status != DocumentStatus.UPLOADING:
        raise HTTPException(
            status_code=409,
            detail=f"New documents must start with status UPLOADING, got {document.status}.",
        )
    ref = get_firestore_client().collection(_COLLECTION).document(document.id)
    ref.set(document.model_dump())
    return document


def update_document_status(
    document_id: str,
    new_status: DocumentStatus,
    owner_uid: str,
    error_message: str | None = None,
) -> Document:
    ref = get_firestore_client().collection(_COLLECTION).document(document_id)
    snap = cast(DocumentSnapshot, ref.get())
    if not snap.exists:
        raise HTTPException(status_code=404, detail="Document not found.")
    doc = _snap_to_doc(snap)
    if doc.owner_uid != owner_uid:
        raise HTTPException(status_code=403, detail="Access denied.")
    if (doc.status, new_status) not in _ALLOWED_TRANSITIONS:
        raise HTTPException(
            status_code=409,
            detail=f"Transition {doc.status} → {new_status} is not allowed.",
        )
    now = _utc_now()
    updates: dict[str, Any] = {"status": new_status.value, "updated_at": now}
    copy_fields: dict[str, Any] = {"status": new_status, "updated_at": now}
    if error_message is not None:
        updates["error_message"] = error_message
        copy_fields["error_message"] = error_message
    ref.update(updates)
    return doc.model_copy(update=copy_fields)


def delete_document(document_id: str, owner_uid: str) -> None:
    ref = get_firestore_client().collection(_COLLECTION).document(document_id)
    snap = cast(DocumentSnapshot, ref.get())
    if not snap.exists:
        raise HTTPException(status_code=404, detail="Document not found.")
    doc = _snap_to_doc(snap)
    if doc.owner_uid != owner_uid:
        raise HTTPException(status_code=403, detail="Access denied.")
    ref.delete()
