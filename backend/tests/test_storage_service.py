"""Tests for storage service — GCS mocked, no network calls."""
from __future__ import annotations

from collections.abc import Generator
from unittest.mock import MagicMock, patch

import pytest
from fastapi import HTTPException

from app.services.storage import delete_file, generate_storage_path, upload_file


# ---------------------------------------------------------------------------
# Fixture
# ---------------------------------------------------------------------------

@pytest.fixture
def mock_bucket() -> Generator[MagicMock, None, None]:
    with patch("app.services.storage.get_storage_bucket") as mock_get:
        bucket = MagicMock()
        mock_get.return_value = bucket
        yield bucket


def _make_blob(mock_bucket: MagicMock, *, exists: bool) -> MagicMock:
    blob = MagicMock()
    blob.exists.return_value = exists
    mock_bucket.blob.return_value = blob
    return blob


# ---------------------------------------------------------------------------
# generate_storage_path — pure function, no fixture needed
# ---------------------------------------------------------------------------

def test_path_format() -> None:
    path = generate_storage_path("uid_abc", "doc_001", "contract.pdf")
    assert path == "documents/uid_abc/doc_001/contract.pdf"


def test_path_starts_with_documents() -> None:
    assert generate_storage_path("u", "d", "f.pdf").startswith("documents/")


def test_path_contains_owner_uid() -> None:
    assert "uid_abc" in generate_storage_path("uid_abc", "d", "f.pdf")


def test_path_contains_document_id() -> None:
    assert "doc_001" in generate_storage_path("u", "doc_001", "f.pdf")


def test_path_contains_filename() -> None:
    assert "contract.pdf" in generate_storage_path("u", "d", "contract.pdf")


def test_path_components_in_order() -> None:
    path = generate_storage_path("owner", "docid", "file.txt")
    parts = path.split("/")
    assert parts == ["documents", "owner", "docid", "file.txt"]


# ---------------------------------------------------------------------------
# upload_file
# ---------------------------------------------------------------------------

def test_upload_returns_storage_path(mock_bucket: MagicMock) -> None:
    _make_blob(mock_bucket, exists=False)
    result = upload_file(b"data", "documents/u/d/f.pdf", "application/pdf")
    assert result == "documents/u/d/f.pdf"


def test_upload_calls_upload_from_string(mock_bucket: MagicMock) -> None:
    blob = _make_blob(mock_bucket, exists=False)
    upload_file(b"hello", "path", "application/pdf")
    blob.upload_from_string.assert_called_once_with(b"hello", content_type="application/pdf")


def test_upload_sets_content_type(mock_bucket: MagicMock) -> None:
    blob = _make_blob(mock_bucket, exists=False)
    upload_file(b"data", "path", "text/plain")
    _, kwargs = blob.upload_from_string.call_args
    assert kwargs["content_type"] == "text/plain"


def test_upload_pdf_content_type(mock_bucket: MagicMock) -> None:
    blob = _make_blob(mock_bucket, exists=False)
    upload_file(b"data", "path", "application/pdf")
    _, kwargs = blob.upload_from_string.call_args
    assert kwargs["content_type"] == "application/pdf"


def test_upload_overwrite_raises_409(mock_bucket: MagicMock) -> None:
    _make_blob(mock_bucket, exists=True)
    with pytest.raises(HTTPException) as exc:
        upload_file(b"data", "path", "application/pdf")
    assert exc.value.status_code == 409


def test_upload_overwrite_does_not_call_upload(mock_bucket: MagicMock) -> None:
    blob = _make_blob(mock_bucket, exists=True)
    with pytest.raises(HTTPException):
        upload_file(b"data", "path", "application/pdf")
    blob.upload_from_string.assert_not_called()


def test_upload_failure_propagates(mock_bucket: MagicMock) -> None:
    blob = _make_blob(mock_bucket, exists=False)
    blob.upload_from_string.side_effect = RuntimeError("GCS unavailable")
    with pytest.raises(RuntimeError, match="GCS unavailable"):
        upload_file(b"data", "path", "application/pdf")


def test_upload_passes_bytes_to_gcs(mock_bucket: MagicMock) -> None:
    blob = _make_blob(mock_bucket, exists=False)
    payload = b"\x89PNG\r\nfake bytes"
    upload_file(payload, "path", "image/png")
    args, _ = blob.upload_from_string.call_args
    assert args[0] == payload


# ---------------------------------------------------------------------------
# delete_file
# ---------------------------------------------------------------------------

def test_delete_existing_file_calls_delete(mock_bucket: MagicMock) -> None:
    blob = _make_blob(mock_bucket, exists=True)
    delete_file("documents/u/d/f.pdf")
    blob.delete.assert_called_once()


def test_delete_missing_file_does_not_raise(mock_bucket: MagicMock) -> None:
    _make_blob(mock_bucket, exists=False)
    delete_file("documents/u/d/missing.pdf")  # must not raise


def test_delete_missing_file_does_not_call_delete(mock_bucket: MagicMock) -> None:
    blob = _make_blob(mock_bucket, exists=False)
    delete_file("documents/u/d/missing.pdf")
    blob.delete.assert_not_called()


def test_delete_idempotent_after_deletion(mock_bucket: MagicMock) -> None:
    blob = MagicMock()
    blob.exists.side_effect = [True, False]
    mock_bucket.blob.return_value = blob
    delete_file("path")
    delete_file("path")
    blob.delete.assert_called_once()


def test_delete_failure_propagates(mock_bucket: MagicMock) -> None:
    blob = _make_blob(mock_bucket, exists=True)
    blob.delete.side_effect = RuntimeError("GCS unavailable")
    with pytest.raises(RuntimeError, match="GCS unavailable"):
        delete_file("path")
