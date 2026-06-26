"""AI Decision Ledger domain models — immutable, append-only, hash-chained."""
from __future__ import annotations

from datetime import datetime
from enum import Enum

from pydantic import BaseModel, ConfigDict, field_serializer, field_validator

# PolicyEffect, PolicyTrigger, PolicyEvaluation, PolicyRecord are defined in
# policy.py (canonical home) and re-exported here for backward compatibility.
from app.models.policy import PolicyEffect as PolicyEffect
from app.models.policy import PolicyEvaluation as PolicyEvaluation
from app.models.policy import PolicyRecord as PolicyRecord
from app.models.policy import PolicyTrigger as PolicyTrigger


# ---------------------------------------------------------------------------
# Enums
# ---------------------------------------------------------------------------


class DecisionKind(str, Enum):
    DECISION   = "decision"
    ANNOTATION = "annotation"
    OVERRIDE   = "override"


class OverrideDisposition(str, Enum):
    REJECTED = "rejected"
    REPLACED = "replaced"
    AMENDED  = "amended"


# ---------------------------------------------------------------------------
# UTC validation helper
# ---------------------------------------------------------------------------


def _require_utc(v: datetime) -> datetime:
    if v.tzinfo is None:
        raise ValueError("timestamp must be timezone-aware")
    offset = v.utcoffset()
    if offset is None or offset.total_seconds() != 0:
        raise ValueError("timestamp must be UTC (zero offset)")
    return v


# ---------------------------------------------------------------------------
# Value objects
# ---------------------------------------------------------------------------


class CachedCitation(BaseModel):
    """Chunk citation snapshotted at decision time."""
    model_config = ConfigDict(frozen=True)

    doc_id:            str
    chunk_index:       int
    page_number:       int | None
    score:             float
    original_filename: str


class RetrievalParams(BaseModel):
    model_config = ConfigDict(frozen=True)

    top_k:           int
    score_threshold: float


class RetrievalRecord(BaseModel):
    model_config = ConfigDict(frozen=True)

    params:    RetrievalParams
    citations: list[CachedCitation]


class MemoryRef(BaseModel):
    """Reference to a Company Legal Memory entry injected at decision time."""
    model_config = ConfigDict(frozen=True)

    entry_id: str
    version:  int
    kind:     str


class ModelParams(BaseModel):
    model_config = ConfigDict(frozen=True)

    name:                    str
    temperature:             float
    max_output_tokens:       int
    prompt_template_version: str


class GroundingStatus(BaseModel):
    """Observable grounding signals from the RAG pipeline (not a calibrated probability)."""
    model_config = ConfigDict(frozen=True)

    citations_above_threshold: int
    top_score:                 float
    disclaimer_emitted:        bool


class OutputRecord(BaseModel):
    model_config = ConfigDict(frozen=True)

    answer_hash:  str   # sha256:<hex> over the delivered answer text
    answer_ref:   str   # cross-reference to the assistant message_id
    sources_used: bool
    grounding:    GroundingStatus


# ---------------------------------------------------------------------------
# Domain models
# ---------------------------------------------------------------------------


class DecisionEvent(BaseModel):
    """Immutable ledger entry for one AI decision (kind=decision).

    Written once at the done seam of the RAG/SSE pipeline; never updated.
    Part of the per-org append-only, hash-chained ledger.
    """
    model_config = ConfigDict(frozen=True)

    id:              str
    org_id:          str
    kind:            DecisionKind
    sequence_no:     int
    actor_uid:       str
    conversation_id: str
    message_id:      str
    query:           str
    document_ids:    list[str]
    language:        str | None       = None
    retrieval:       RetrievalRecord
    memory_used:     list[MemoryRef]
    model:           ModelParams
    policy:          PolicyRecord
    output:          OutputRecord
    prev_hash:       str
    entry_hash:      str
    created_at:      datetime

    @field_validator("created_at")
    @classmethod
    def must_be_utc(cls, v: datetime) -> datetime:
        return _require_utc(v)

    @field_serializer("created_at")
    def serialize_dt(self, v: datetime) -> str:
        return v.isoformat().replace("+00:00", "Z")


class HumanOverride(BaseModel):
    """Immutable ledger entry recording a human override of an AI recommendation.

    kind must be OVERRIDE. One entry per human action; the original DecisionEvent
    is never modified. Override history is itself tamper-evident via the hash chain.
    """
    model_config = ConfigDict(frozen=True)

    id:                      str
    org_id:                  str
    kind:                    DecisionKind
    sequence_no:             int
    actor_uid:               str
    conversation_id:         str
    decision_id:             str              # ledger entry_id being overridden
    approver:                str              # uid of the human who overrode
    reason:                  str
    previous_recommendation: str             # answer_hash of the original output
    final_outcome:           str
    disposition:             OverrideDisposition
    prev_hash:               str
    entry_hash:              str
    created_at:              datetime

    @field_validator("kind")
    @classmethod
    def must_be_override_kind(cls, v: DecisionKind) -> DecisionKind:
        if v != DecisionKind.OVERRIDE:
            raise ValueError("kind must be 'override' for HumanOverride")
        return v

    @field_validator("created_at")
    @classmethod
    def must_be_utc(cls, v: datetime) -> datetime:
        return _require_utc(v)

    @field_serializer("created_at")
    def serialize_dt(self, v: datetime) -> str:
        return v.isoformat().replace("+00:00", "Z")


class DecisionAnnotation(BaseModel):
    """Immutable ledger entry annotating or correcting an existing decision.

    kind must be ANNOTATION. Corrections are new entries that supersede;
    the original DecisionEvent is preserved unchanged.
    """
    model_config = ConfigDict(frozen=True)

    id:              str
    org_id:          str
    kind:            DecisionKind
    sequence_no:     int
    actor_uid:       str
    conversation_id: str
    decision_id:     str   # ledger entry_id being annotated
    original_hash:   str   # entry_hash of the original decision for cross-verification
    note:            str
    prev_hash:       str
    entry_hash:      str
    created_at:      datetime

    @field_validator("kind")
    @classmethod
    def must_be_annotation_kind(cls, v: DecisionKind) -> DecisionKind:
        if v != DecisionKind.ANNOTATION:
            raise ValueError("kind must be 'annotation' for DecisionAnnotation")
        return v

    @field_validator("created_at")
    @classmethod
    def must_be_utc(cls, v: datetime) -> datetime:
        return _require_utc(v)

    @field_serializer("created_at")
    def serialize_dt(self, v: datetime) -> str:
        return v.isoformat().replace("+00:00", "Z")
