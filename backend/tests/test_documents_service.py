"""Tests for documents service — Firestore mocked, no network calls."""
from __future__ import annotations

from collections.abc import Generator
from datetime import datetime, timedelta, timezone
from unittest.mock import MagicMock, patch

import pytest
from fastapi import HTTPException

from app.models.document import Document, DocumentStatus
from app.services.documents import (
    create_document,
    delete_document,
    get_document,
    list_documents,
    update_document_status,
)

UTC = timezone.utc
_T0 = datetime(2024, 6, 1, 12, 0, 0, tzinfo=UTC)

_STORED: dict[str, object] = {
    "id": "doc_001",
    "owner_uid": "uid_abc",
    "filename": "contract.pdf",
    "original_filename": "Contract (2024).pdf",
    "mime_type": "application/pdf",
    "size_bytes": 204800,
    "status": "UPLOADING",
    "storage_path": "users/uid_abc/documents/doc_001/contract.pdf",
    "created_at": _T0,
    "updated_at": _T0,
}


def _data(**overrides: object) -> dict[str, object]:
    d = dict(_STORED)
    d.update(overrides)
    return d


def _doc(**overrides: object) -> Document:
    return Document(**_data(**overrides))  # type: ignore[arg-type]


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------

@pytest.fixture
def mock_db() -> Generator[MagicMock, None, None]:
    with patch("app.services.documents.get_firestore_client") as mock_get:
        mock_client = MagicMock()
        mock_get.return_value = mock_client
        yield mock_client


def _make_ref(mock_db: MagicMock, exists: bool, data: dict[str, object] | None = None) -> MagicMock:
    """Wire mock_db.collection.document chain for get/update/delete operations."""
    snap = MagicMock()
    snap.exists = exists
    snap.to_dict.return_value = data if exists else None
    ref = MagicMock()
    ref.get.return_value = snap
    mock_db.collection.return_value.document.return_value = ref
    return ref


def _make_snap(data: dict[str, object]) -> MagicMock:
    """Single snapshot for list query results."""
    snap = MagicMock()
    snap.exists = True
    snap.to_dict.return_value = data
    return snap


# ---------------------------------------------------------------------------
# create_document
# ---------------------------------------------------------------------------

def test_create_returns_document(mock_db: MagicMock) -> None:
    _make_ref(mock_db, exists=False)
    result = create_document(_doc(status="UPLOADING"))
    assert result.id == "doc_001"
    assert result.status == DocumentStatus.UPLOADING


def test_create_calls_firestore_set(mock_db: MagicMock) -> None:
    ref = _make_ref(mock_db, exists=False)
    create_document(_doc(status="UPLOADING"))
    ref.set.assert_called_once()


def test_create_rejects_ready_status(mock_db: MagicMock) -> None:
    with pytest.raises(HTTPException) as exc:
        create_document(_doc(status="READY"))
    assert exc.value.status_code == 409


def test_create_rejects_processing_status(mock_db: MagicMock) -> None:
    with pytest.raises(HTTPException) as exc:
        create_document(_doc(status="PROCESSING"))
    assert exc.value.status_code == 409


# ---------------------------------------------------------------------------
# get_document
# ---------------------------------------------------------------------------

def test_get_returns_document(mock_db: MagicMock) -> None:
    _make_ref(mock_db, exists=True, data=_data())
    doc = get_document("doc_001", "uid_abc")
    assert doc.id == "doc_001"
    assert doc.owner_uid == "uid_abc"


def test_get_not_found_raises_404(mock_db: MagicMock) -> None:
    _make_ref(mock_db, exists=False)
    with pytest.raises(HTTPException) as exc:
        get_document("missing", "uid_abc")
    assert exc.value.status_code == 404


def test_get_wrong_owner_raises_403(mock_db: MagicMock) -> None:
    _make_ref(mock_db, exists=True, data=_data(owner_uid="uid_abc"))
    with pytest.raises(HTTPException) as exc:
        get_document("doc_001", "uid_attacker")
    assert exc.value.status_code == 403


# ---------------------------------------------------------------------------
# list_documents
# ---------------------------------------------------------------------------

def test_list_returns_documents_for_owner(mock_db: MagicMock) -> None:
    mock_db.collection.return_value.where.return_value.stream.return_value = [_make_snap(_data())]
    result = list_documents("uid_abc")
    assert len(result) == 1
    assert result[0].id == "doc_001"


def test_list_empty_returns_empty_list(mock_db: MagicMock) -> None:
    mock_db.collection.return_value.where.return_value.stream.return_value = []
    assert list_documents("uid_abc") == []


def test_list_ordered_by_updated_at_desc(mock_db: MagicMock) -> None:
    earlier = _T0
    later = _T0 + timedelta(days=1)
    snap_older = _make_snap(_data(id="old_doc", updated_at=earlier))
    snap_newer = _make_snap(_data(id="new_doc", updated_at=later))
    # Return in wrong order (older first) to verify sorting is applied
    mock_db.collection.return_value.where.return_value.stream.return_value = [snap_older, snap_newer]
    result = list_documents("uid_abc")
    assert result[0].id == "new_doc"
    assert result[1].id == "old_doc"


def test_list_returns_document_instances(mock_db: MagicMock) -> None:
    mock_db.collection.return_value.where.return_value.stream.return_value = [_make_snap(_data())]
    result = list_documents("uid_abc")
    assert all(isinstance(d, Document) for d in result)


# ---------------------------------------------------------------------------
# delete_document
# ---------------------------------------------------------------------------

def test_delete_calls_firestore_delete(mock_db: MagicMock) -> None:
    ref = _make_ref(mock_db, exists=True, data=_data())
    delete_document("doc_001", "uid_abc")
    ref.delete.assert_called_once()


def test_delete_not_found_raises_404(mock_db: MagicMock) -> None:
    _make_ref(mock_db, exists=False)
    with pytest.raises(HTTPException) as exc:
        delete_document("missing", "uid_abc")
    assert exc.value.status_code == 404


def test_delete_wrong_owner_raises_403(mock_db: MagicMock) -> None:
    _make_ref(mock_db, exists=True, data=_data(owner_uid="uid_abc"))
    with pytest.raises(HTTPException) as exc:
        delete_document("doc_001", "uid_attacker")
    assert exc.value.status_code == 403


def test_delete_wrong_owner_does_not_call_delete(mock_db: MagicMock) -> None:
    ref = _make_ref(mock_db, exists=True, data=_data(owner_uid="uid_abc"))
    with pytest.raises(HTTPException):
        delete_document("doc_001", "uid_attacker")
    ref.delete.assert_not_called()


# ---------------------------------------------------------------------------
# update_document_status — valid transitions
# ---------------------------------------------------------------------------

def _update(mock_db: MagicMock, from_status: str, to_status: DocumentStatus) -> Document:
    _make_ref(mock_db, exists=True, data=_data(status=from_status))
    return update_document_status("doc_001", to_status, "uid_abc")


def test_uploading_to_processing_allowed(mock_db: MagicMock) -> None:
    result = _update(mock_db, "UPLOADING", DocumentStatus.PROCESSING)
    assert result.status == DocumentStatus.PROCESSING


def test_uploading_to_failed_allowed(mock_db: MagicMock) -> None:
    result = _update(mock_db, "UPLOADING", DocumentStatus.FAILED)
    assert result.status == DocumentStatus.FAILED


def test_processing_to_ready_allowed(mock_db: MagicMock) -> None:
    result = _update(mock_db, "PROCESSING", DocumentStatus.READY)
    assert result.status == DocumentStatus.READY


def test_processing_to_failed_allowed(mock_db: MagicMock) -> None:
    result = _update(mock_db, "PROCESSING", DocumentStatus.FAILED)
    assert result.status == DocumentStatus.FAILED


def test_update_calls_firestore_update(mock_db: MagicMock) -> None:
    ref = _make_ref(mock_db, exists=True, data=_data(status="UPLOADING"))
    update_document_status("doc_001", DocumentStatus.PROCESSING, "uid_abc")
    ref.update.assert_called_once()


def test_update_sets_updated_at(mock_db: MagicMock) -> None:
    result = _update(mock_db, "UPLOADING", DocumentStatus.PROCESSING)
    assert result.updated_at > _T0


# ---------------------------------------------------------------------------
# update_document_status — invalid transitions (409)
# ---------------------------------------------------------------------------

def _assert_transition_rejected(
    mock_db: MagicMock, from_status: str, to_status: DocumentStatus
) -> None:
    _make_ref(mock_db, exists=True, data=_data(status=from_status))
    with pytest.raises(HTTPException) as exc:
        update_document_status("doc_001", to_status, "uid_abc")
    assert exc.value.status_code == 409


def test_ready_to_processing_rejected(mock_db: MagicMock) -> None:
    _assert_transition_rejected(mock_db, "READY", DocumentStatus.PROCESSING)


def test_ready_to_failed_rejected(mock_db: MagicMock) -> None:
    _assert_transition_rejected(mock_db, "READY", DocumentStatus.FAILED)


def test_ready_to_uploading_rejected(mock_db: MagicMock) -> None:
    _assert_transition_rejected(mock_db, "READY", DocumentStatus.UPLOADING)


def test_failed_to_ready_rejected(mock_db: MagicMock) -> None:
    _assert_transition_rejected(mock_db, "FAILED", DocumentStatus.READY)


def test_failed_to_processing_rejected(mock_db: MagicMock) -> None:
    _assert_transition_rejected(mock_db, "FAILED", DocumentStatus.PROCESSING)


def test_failed_to_uploading_rejected(mock_db: MagicMock) -> None:
    _assert_transition_rejected(mock_db, "FAILED", DocumentStatus.UPLOADING)


def test_processing_to_uploading_rejected(mock_db: MagicMock) -> None:
    _assert_transition_rejected(mock_db, "PROCESSING", DocumentStatus.UPLOADING)


def test_uploading_to_ready_rejected(mock_db: MagicMock) -> None:
    _assert_transition_rejected(mock_db, "UPLOADING", DocumentStatus.READY)


# ---------------------------------------------------------------------------
# update_document_status — ownership + not found
# ---------------------------------------------------------------------------

def test_update_not_found_raises_404(mock_db: MagicMock) -> None:
    _make_ref(mock_db, exists=False)
    with pytest.raises(HTTPException) as exc:
        update_document_status("missing", DocumentStatus.PROCESSING, "uid_abc")
    assert exc.value.status_code == 404


def test_update_wrong_owner_raises_403(mock_db: MagicMock) -> None:
    _make_ref(mock_db, exists=True, data=_data(owner_uid="uid_abc", status="UPLOADING"))
    with pytest.raises(HTTPException) as exc:
        update_document_status("doc_001", DocumentStatus.PROCESSING, "uid_attacker")
    assert exc.value.status_code == 403
