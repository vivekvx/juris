"""File storage service — GCS blob operations only.

No Firestore. No Document model. No metadata.
Pure bytes ↔ GCS abstraction over get_storage_bucket().
"""
from __future__ import annotations

from fastapi import HTTPException

from app.core.firebase import get_storage_bucket


def generate_storage_path(owner_uid: str, document_id: str, filename: str) -> str:
    return f"documents/{owner_uid}/{document_id}/{filename}"


def upload_file(data: bytes, storage_path: str, mime_type: str) -> str:
    bucket = get_storage_bucket()
    blob = bucket.blob(storage_path)
    if blob.exists():
        raise HTTPException(
            status_code=409,
            detail=f"File already exists at {storage_path!r}. Overwrite is not allowed.",
        )
    blob.upload_from_string(data, content_type=mime_type)
    return storage_path


def delete_file(storage_path: str) -> None:
    bucket = get_storage_bucket()
    blob = bucket.blob(storage_path)
    if not blob.exists():
        return
    blob.delete()
