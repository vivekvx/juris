from __future__ import annotations

from datetime import datetime
from enum import Enum

from pydantic import BaseModel, ConfigDict, field_serializer, field_validator


class DocumentStatus(str, Enum):
    UPLOADING  = "UPLOADING"
    PROCESSING = "PROCESSING"
    READY      = "READY"
    FAILED     = "FAILED"


class Document(BaseModel):
    model_config = ConfigDict(frozen=True)

    id:                str
    owner_uid:         str
    filename:          str
    original_filename: str
    mime_type:         str
    size_bytes:        int
    status:            DocumentStatus
    storage_path:      str
    created_at:        datetime
    updated_at:        datetime

    @field_validator("created_at", "updated_at")
    @classmethod
    def must_be_utc(cls, v: datetime) -> datetime:
        if v.tzinfo is None:
            raise ValueError("timestamp must be timezone-aware")
        offset = v.utcoffset()
        if offset is None or offset.total_seconds() != 0:
            raise ValueError("timestamp must be UTC (zero offset)")
        return v

    @field_serializer("created_at", "updated_at")
    def serialize_dt(self, v: datetime) -> str:
        return v.isoformat().replace("+00:00", "Z")
