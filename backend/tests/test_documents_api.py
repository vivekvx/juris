"""Tests for POST /api/documents — Firestore and GCS mocked, no network calls."""
from __future__ import annotations

from collections.abc import Generator
from datetime import datetime, timezone
from unittest.mock import MagicMock, patch

import pytest
from fastapi.testclient import TestClient

from app.core.auth import get_current_user
from app.main import create_app
from app.models.document import Document, DocumentStatus
from app.models.user import User

UTC = timezone.utc
_NOW = datetime(2024, 6, 1, 12, 0, 0, tzinfo=UTC)
_USER = User(uid="uid_abc", email="test@example.com", display_name=None, photo_url=None)
_FIXED_ID = "test-doc-uuid-0001"
_STORAGE_PATH = f"documents/uid_abc/{_FIXED_ID}/contract.pdf"

PDF_BYTES = b"%PDF-1.4 fake pdf content"
DOCX_BYTES = b"PK\x03\x04fake docx content"
TXT_BYTES = b"Plain text content"


def _make_doc(**overrides: object) -> Document:
    base: dict[str, object] = {
        "id": _FIXED_ID,
        "owner_uid": "uid_abc",
        "filename": "contract.pdf",
        "original_filename": "contract.pdf",
        "mime_type": "application/pdf",
        "size_bytes": len(PDF_BYTES),
        "status": DocumentStatus.UPLOADING,
        "storage_path": _STORAGE_PATH,
        "created_at": _NOW,
        "updated_at": _NOW,
    }
    base.update(overrides)
    return Document(**base)  # type: ignore[arg-type]


@pytest.fixture
def client() -> Generator[TestClient, None, None]:
    app = create_app()
    app.dependency_overrides[get_current_user] = lambda: _USER
    with TestClient(app) as c:
        yield c


def _patch_services(
    mock_create: MagicMock,
    mock_upload: MagicMock,
    mock_update: MagicMock,
) -> None:
    mock_create.side_effect = lambda doc: doc
    mock_upload.return_value = _STORAGE_PATH
    mock_update.side_effect = [
        _make_doc(status=DocumentStatus.PROCESSING),
        _make_doc(status=DocumentStatus.READY),
    ]


# ---------------------------------------------------------------------------
# Successful upload — all three accepted MIME types
# ---------------------------------------------------------------------------

def test_upload_pdf_returns_201(client: TestClient) -> None:
    with (
        patch("app.api.documents.create_document") as mc,
        patch("app.api.documents.upload_file") as mu,
        patch("app.api.documents.update_document_status") as mupd,
    ):
        _patch_services(mc, mu, mupd)
        response = client.post(
            "/api/documents/",
            files={"file": ("contract.pdf", PDF_BYTES, "application/pdf")},
        )
    assert response.status_code == 201


def test_upload_docx_returns_201(client: TestClient) -> None:
    _docx = "application/vnd.openxmlformats-officedocument.wordprocessingml.document"
    with (
        patch("app.api.documents.create_document") as mc,
        patch("app.api.documents.upload_file") as mu,
        patch("app.api.documents.update_document_status") as mupd,
    ):
        mc.side_effect = lambda doc: doc
        mu.return_value = _STORAGE_PATH
        mupd.side_effect = [
            _make_doc(mime_type=_docx, status=DocumentStatus.PROCESSING),
            _make_doc(mime_type=_docx, status=DocumentStatus.READY),
        ]
        response = client.post(
            "/api/documents/",
            files={"file": ("draft.docx", DOCX_BYTES, _docx)},
        )
    assert response.status_code == 201


def test_upload_txt_returns_201(client: TestClient) -> None:
    with (
        patch("app.api.documents.create_document") as mc,
        patch("app.api.documents.upload_file") as mu,
        patch("app.api.documents.update_document_status") as mupd,
    ):
        mc.side_effect = lambda doc: doc
        mu.return_value = _STORAGE_PATH
        mupd.side_effect = [
            _make_doc(mime_type="text/plain", status=DocumentStatus.PROCESSING),
            _make_doc(mime_type="text/plain", status=DocumentStatus.READY),
        ]
        response = client.post(
            "/api/documents/",
            files={"file": ("notes.txt", TXT_BYTES, "text/plain")},
        )
    assert response.status_code == 201


# ---------------------------------------------------------------------------
# Typed response shape
# ---------------------------------------------------------------------------

def test_upload_returns_typed_response(client: TestClient) -> None:
    with (
        patch("app.api.documents.create_document") as mc,
        patch("app.api.documents.upload_file") as mu,
        patch("app.api.documents.update_document_status") as mupd,
    ):
        _patch_services(mc, mu, mupd)
        response = client.post(
            "/api/documents/",
            files={"file": ("contract.pdf", PDF_BYTES, "application/pdf")},
        )
    body = response.json()
    assert isinstance(body["id"], str)
    assert isinstance(body["filename"], str)
    assert isinstance(body["original_filename"], str)
    assert isinstance(body["mime_type"], str)
    assert isinstance(body["size_bytes"], int)
    assert "status" in body
    assert "error_message" in body
    assert isinstance(body["created_at"], str)
    assert isinstance(body["updated_at"], str)


def test_upload_response_status_is_ready(client: TestClient) -> None:
    with (
        patch("app.api.documents.create_document") as mc,
        patch("app.api.documents.upload_file") as mu,
        patch("app.api.documents.update_document_status") as mupd,
    ):
        _patch_services(mc, mu, mupd)
        response = client.post(
            "/api/documents/",
            files={"file": ("contract.pdf", PDF_BYTES, "application/pdf")},
        )
    assert response.json()["status"] == "READY"


def test_upload_response_timestamps_end_in_z(client: TestClient) -> None:
    with (
        patch("app.api.documents.create_document") as mc,
        patch("app.api.documents.upload_file") as mu,
        patch("app.api.documents.update_document_status") as mupd,
    ):
        _patch_services(mc, mu, mupd)
        response = client.post(
            "/api/documents/",
            files={"file": ("contract.pdf", PDF_BYTES, "application/pdf")},
        )
    body = response.json()
    assert body["created_at"].endswith("Z")
    assert body["updated_at"].endswith("Z")


def test_upload_response_error_message_none_on_success(client: TestClient) -> None:
    with (
        patch("app.api.documents.create_document") as mc,
        patch("app.api.documents.upload_file") as mu,
        patch("app.api.documents.update_document_status") as mupd,
    ):
        _patch_services(mc, mu, mupd)
        response = client.post(
            "/api/documents/",
            files={"file": ("contract.pdf", PDF_BYTES, "application/pdf")},
        )
    assert response.json()["error_message"] is None


# ---------------------------------------------------------------------------
# Status transitions
# ---------------------------------------------------------------------------

def test_transitions_uploading_processing_ready(client: TestClient) -> None:
    with (
        patch("app.api.documents.create_document") as mc,
        patch("app.api.documents.upload_file") as mu,
        patch("app.api.documents.update_document_status") as mupd,
    ):
        _patch_services(mc, mu, mupd)
        client.post(
            "/api/documents/",
            files={"file": ("contract.pdf", PDF_BYTES, "application/pdf")},
        )
    calls = mupd.call_args_list
    assert len(calls) == 2
    assert calls[0].args[1] == DocumentStatus.PROCESSING
    assert calls[1].args[1] == DocumentStatus.READY


def test_create_document_called_with_uploading_status(client: TestClient) -> None:
    with (
        patch("app.api.documents.create_document") as mc,
        patch("app.api.documents.upload_file") as mu,
        patch("app.api.documents.update_document_status") as mupd,
    ):
        _patch_services(mc, mu, mupd)
        client.post(
            "/api/documents/",
            files={"file": ("contract.pdf", PDF_BYTES, "application/pdf")},
        )
    created_doc: Document = mc.call_args.args[0]
    assert created_doc.status == DocumentStatus.UPLOADING


# ---------------------------------------------------------------------------
# Storage failure — FAILED path
# ---------------------------------------------------------------------------

def test_storage_failure_returns_503(client: TestClient) -> None:
    with (
        patch("app.api.documents.create_document") as mc,
        patch("app.api.documents.upload_file") as mu,
        patch("app.api.documents.update_document_status") as mupd,
    ):
        mc.side_effect = lambda doc: doc
        mu.side_effect = RuntimeError("GCS unavailable")
        mupd.return_value = _make_doc(status=DocumentStatus.FAILED)
        response = client.post(
            "/api/documents/",
            files={"file": ("contract.pdf", PDF_BYTES, "application/pdf")},
        )
    assert response.status_code == 503


def test_storage_failure_marks_document_failed(client: TestClient) -> None:
    with (
        patch("app.api.documents.create_document") as mc,
        patch("app.api.documents.upload_file") as mu,
        patch("app.api.documents.update_document_status") as mupd,
    ):
        mc.side_effect = lambda doc: doc
        mu.side_effect = RuntimeError("GCS unavailable")
        mupd.return_value = _make_doc(status=DocumentStatus.FAILED)
        client.post(
            "/api/documents/",
            files={"file": ("contract.pdf", PDF_BYTES, "application/pdf")},
        )
    mupd.assert_called_once()
    assert mupd.call_args.args[1] == DocumentStatus.FAILED


def test_storage_failure_passes_error_message(client: TestClient) -> None:
    with (
        patch("app.api.documents.create_document") as mc,
        patch("app.api.documents.upload_file") as mu,
        patch("app.api.documents.update_document_status") as mupd,
    ):
        mc.side_effect = lambda doc: doc
        mu.side_effect = RuntimeError("disk full")
        mupd.return_value = _make_doc(status=DocumentStatus.FAILED)
        client.post(
            "/api/documents/",
            files={"file": ("contract.pdf", PDF_BYTES, "application/pdf")},
        )
    assert mupd.call_args.kwargs.get("error_message") is not None


def test_storage_failure_skips_processing_and_ready(client: TestClient) -> None:
    with (
        patch("app.api.documents.create_document") as mc,
        patch("app.api.documents.upload_file") as mu,
        patch("app.api.documents.update_document_status") as mupd,
    ):
        mc.side_effect = lambda doc: doc
        mu.side_effect = RuntimeError("GCS unavailable")
        mupd.return_value = _make_doc(status=DocumentStatus.FAILED)
        client.post(
            "/api/documents/",
            files={"file": ("contract.pdf", PDF_BYTES, "application/pdf")},
        )
    statuses = [c.args[1] for c in mupd.call_args_list]
    assert DocumentStatus.PROCESSING not in statuses
    assert DocumentStatus.READY not in statuses


# ---------------------------------------------------------------------------
# Validation — unsupported type
# ---------------------------------------------------------------------------

def test_unsupported_mime_returns_415(client: TestClient) -> None:
    response = client.post(
        "/api/documents/",
        files={"file": ("photo.jpg", b"\xff\xd8fake", "image/jpeg")},
    )
    assert response.status_code == 415


def test_unsupported_mime_no_firestore_write(client: TestClient) -> None:
    with patch("app.api.documents.create_document") as mc:
        client.post(
            "/api/documents/",
            files={"file": ("photo.jpg", b"\xff\xd8fake", "image/jpeg")},
        )
    mc.assert_not_called()


def test_unsupported_mime_no_storage_write(client: TestClient) -> None:
    with patch("app.api.documents.upload_file") as mu:
        client.post(
            "/api/documents/",
            files={"file": ("photo.jpg", b"\xff\xd8fake", "image/jpeg")},
        )
    mu.assert_not_called()


# ---------------------------------------------------------------------------
# Validation — oversized file
# ---------------------------------------------------------------------------

def test_oversized_file_returns_413(client: TestClient) -> None:
    big = b"x" * (20 * 1024 * 1024 + 1)
    response = client.post(
        "/api/documents/",
        files={"file": ("big.pdf", big, "application/pdf")},
    )
    assert response.status_code == 413


def test_oversized_file_no_firestore_write(client: TestClient) -> None:
    big = b"x" * (20 * 1024 * 1024 + 1)
    with patch("app.api.documents.create_document") as mc:
        client.post(
            "/api/documents/",
            files={"file": ("big.pdf", big, "application/pdf")},
        )
    mc.assert_not_called()


def test_oversized_file_no_storage_write(client: TestClient) -> None:
    big = b"x" * (20 * 1024 * 1024 + 1)
    with patch("app.api.documents.upload_file") as mu:
        client.post(
            "/api/documents/",
            files={"file": ("big.pdf", big, "application/pdf")},
        )
    mu.assert_not_called()


# ---------------------------------------------------------------------------
# Authentication
# ---------------------------------------------------------------------------

def test_upload_requires_authentication() -> None:
    app = create_app()  # no dependency override
    with TestClient(app) as unauthenticated:
        response = unauthenticated.post(
            "/api/documents/",
            files={"file": ("contract.pdf", PDF_BYTES, "application/pdf")},
        )
    assert response.status_code == 401
