from __future__ import annotations

from datetime import datetime

from pydantic import BaseModel, ConfigDict, field_validator

CURRENT_CHUNK_VERSION = 1
EMBEDDING_MODEL = "text-embedding-004"


class Chunk(BaseModel):
    model_config = ConfigDict(frozen=True)

    id:              str
    doc_id:          str
    owner_uid:       str
    content:         str
    embedding:       list[float]
    chunk_index:     int
    page_number:     int | None
    token_count:     int
    chunk_version:   int
    embedding_model: str
    created_at:      datetime

    @field_validator("created_at")
    @classmethod
    def must_be_utc(cls, v: datetime) -> datetime:
        if v.tzinfo is None:
            raise ValueError("timestamp must be timezone-aware")
        offset = v.utcoffset()
        if offset is None or offset.total_seconds() != 0:
            raise ValueError("timestamp must be UTC")
        return v


class ChunkCitation(BaseModel):
    doc_id:            str
    original_filename: str
    chunk_index:       int
    page_number:       int | None
    content:           str
    score:             float
