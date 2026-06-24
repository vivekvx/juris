from __future__ import annotations

from datetime import datetime
from typing import Literal

from pydantic import BaseModel, ConfigDict, field_serializer, field_validator


class Conversation(BaseModel):
    model_config = ConfigDict(frozen=True)

    id: str
    owner_uid: str
    title: str
    created_at: datetime
    updated_at: datetime
    last_message_at: datetime | None = None
    document_ids: list[str] | None = None
    title_generated: bool = False

    @field_validator("created_at", "updated_at")
    @classmethod
    def must_be_utc(cls, v: datetime) -> datetime:
        if v.tzinfo is None:
            raise ValueError("timestamp must be timezone-aware")
        offset = v.utcoffset()
        if offset is None or offset.total_seconds() != 0:
            raise ValueError("timestamp must be UTC (zero offset)")
        return v

    @field_validator("last_message_at")
    @classmethod
    def last_message_at_must_be_utc(cls, v: datetime | None) -> datetime | None:
        if v is None:
            return None
        if v.tzinfo is None:
            raise ValueError("timestamp must be timezone-aware")
        offset = v.utcoffset()
        if offset is None or offset.total_seconds() != 0:
            raise ValueError("timestamp must be UTC (zero offset)")
        return v

    @field_serializer("created_at", "updated_at")
    def serialize_dt(self, v: datetime) -> str:
        return v.isoformat().replace("+00:00", "Z")

    @field_serializer("last_message_at")
    def serialize_last_message_at(self, v: datetime | None) -> str | None:
        if v is None:
            return None
        return v.isoformat().replace("+00:00", "Z")


class Message(BaseModel):
    model_config = ConfigDict(frozen=True)

    id: str
    role: Literal["user", "assistant"]
    content: str
    created_at: datetime
    citations: list[dict[str, object]] | None = None

    @field_validator("created_at")
    @classmethod
    def must_be_utc(cls, v: datetime) -> datetime:
        if v.tzinfo is None:
            raise ValueError("timestamp must be timezone-aware")
        offset = v.utcoffset()
        if offset is None or offset.total_seconds() != 0:
            raise ValueError("timestamp must be UTC (zero offset)")
        return v

    @field_serializer("created_at")
    def serialize_dt(self, v: datetime) -> str:
        return v.isoformat().replace("+00:00", "Z")
