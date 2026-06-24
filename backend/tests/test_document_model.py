"""Pure model tests for Document and DocumentStatus — no mocks, no network."""
from __future__ import annotations

import json
from datetime import datetime, timedelta, timezone

import pytest
from pydantic import ValidationError

from app.models.document import Document, DocumentStatus

UTC = timezone.utc
_T0 = datetime(2024, 6, 1, 12, 0, 0, tzinfo=UTC)


def _doc(**overrides: object) -> Document:
    base: dict[str, object] = dict(
        id="doc_001",
        owner_uid="uid_abc",
        filename="contract.pdf",
        original_filename="My Contract (2024).pdf",
        mime_type="application/pdf",
        size_bytes=204800,
        status=DocumentStatus.READY,
        storage_path="users/uid_abc/documents/doc_001/contract.pdf",
        created_at=_T0,
        updated_at=_T0,
    )
    base.update(overrides)
    return Document(**base)  # type: ignore[arg-type]


# ---------------------------------------------------------------------------
# Enum values
# ---------------------------------------------------------------------------

def test_status_uploading_value() -> None:
    assert DocumentStatus.UPLOADING == "UPLOADING"


def test_status_processing_value() -> None:
    assert DocumentStatus.PROCESSING == "PROCESSING"


def test_status_ready_value() -> None:
    assert DocumentStatus.READY == "READY"


def test_status_failed_value() -> None:
    assert DocumentStatus.FAILED == "FAILED"


def test_status_exactly_four_members() -> None:
    assert {s.value for s in DocumentStatus} == {"UPLOADING", "PROCESSING", "READY", "FAILED"}


def test_status_is_string_subtype() -> None:
    assert isinstance(DocumentStatus.READY, str)


# ---------------------------------------------------------------------------
# Valid construction
# ---------------------------------------------------------------------------

def test_document_constructs() -> None:
    doc = _doc()
    assert doc.id == "doc_001"
    assert doc.owner_uid == "uid_abc"
    assert doc.status == DocumentStatus.READY


def test_document_dump_contains_all_fields() -> None:
    keys = set(_doc().model_dump().keys())
    assert keys == {
        "id", "owner_uid", "filename", "original_filename",
        "mime_type", "size_bytes", "status", "storage_path",
        "error_message", "created_at", "updated_at",
        "processing_warning", "indexed_at", "processing_started_at", "chunk_count",
    }


def test_status_accepted_from_string() -> None:
    doc = _doc(status="UPLOADING")
    assert doc.status == DocumentStatus.UPLOADING


# ---------------------------------------------------------------------------
# Serialization
# ---------------------------------------------------------------------------

def test_status_serializes_as_string() -> None:
    dumped = _doc().model_dump()
    assert dumped["status"] == "READY"
    assert isinstance(dumped["status"], str)


def test_json_is_valid() -> None:
    parsed = json.loads(_doc().model_dump_json())
    assert parsed["id"] == "doc_001"


def test_json_timestamps_end_in_z() -> None:
    parsed = json.loads(_doc().model_dump_json())
    assert parsed["created_at"].endswith("Z")
    assert parsed["updated_at"].endswith("Z")


def test_json_timestamps_no_offset_notation() -> None:
    raw = _doc().model_dump_json()
    assert "+00:00" not in raw


def test_timestamp_format_exact() -> None:
    doc = _doc(created_at=datetime(2024, 1, 15, 9, 30, 0, tzinfo=UTC))
    parsed = json.loads(doc.model_dump_json())
    assert parsed["created_at"] == "2024-01-15T09:30:00Z"


def test_timestamp_with_microseconds_ends_in_z() -> None:
    doc = _doc(created_at=datetime(2024, 1, 15, 9, 30, 0, 500000, tzinfo=UTC))
    parsed = json.loads(doc.model_dump_json())
    assert parsed["created_at"].endswith("Z")
    assert "+00:00" not in parsed["created_at"]


# ---------------------------------------------------------------------------
# Timestamp validation
# ---------------------------------------------------------------------------

def test_naive_created_at_rejected() -> None:
    with pytest.raises(ValidationError, match="timezone-aware"):
        _doc(created_at=datetime(2024, 1, 1))


def test_naive_updated_at_rejected() -> None:
    with pytest.raises(ValidationError, match="timezone-aware"):
        _doc(updated_at=datetime(2024, 1, 1))


def test_non_utc_timezone_rejected() -> None:
    ist = timezone(timedelta(hours=5, minutes=30))
    with pytest.raises(ValidationError, match="UTC"):
        _doc(created_at=datetime(2024, 1, 1, 12, 0, 0, tzinfo=ist))


def test_negative_offset_timezone_rejected() -> None:
    est = timezone(timedelta(hours=-5))
    with pytest.raises(ValidationError, match="UTC"):
        _doc(updated_at=datetime(2024, 1, 1, 12, 0, 0, tzinfo=est))


# ---------------------------------------------------------------------------
# Field validation
# ---------------------------------------------------------------------------

def test_invalid_status_string_rejected() -> None:
    with pytest.raises(ValidationError):
        _doc(status="UNKNOWN")


def test_size_bytes_must_be_int() -> None:
    with pytest.raises(ValidationError):
        _doc(size_bytes="big")


# ---------------------------------------------------------------------------
# Immutability
# ---------------------------------------------------------------------------

def test_storage_path_immutable() -> None:
    doc = _doc()
    with pytest.raises((ValidationError, TypeError)):
        doc.storage_path = "new/path"

def test_owner_uid_immutable() -> None:
    doc = _doc()
    with pytest.raises((ValidationError, TypeError)):
        doc.owner_uid = "attacker_uid"

def test_created_at_immutable() -> None:
    doc = _doc()
    with pytest.raises((ValidationError, TypeError)):
        doc.created_at = datetime(2099, 1, 1, tzinfo=UTC)

def test_id_immutable() -> None:
    doc = _doc()
    with pytest.raises((ValidationError, TypeError)):
        doc.id = "new_id"

def test_updated_at_mutable_via_copy() -> None:
    doc = _doc()
    new_time = datetime(2025, 6, 1, tzinfo=UTC)
    updated = doc.model_copy(update={"updated_at": new_time})
    assert updated.updated_at == new_time


def test_copy_does_not_mutate_original() -> None:
    doc = _doc()
    new_time = datetime(2025, 6, 1, tzinfo=UTC)
    doc.model_copy(update={"updated_at": new_time})
    assert doc.updated_at == _T0
