"""Policy Engine domain models — declarative governance over the AI pipeline."""
from __future__ import annotations

from datetime import datetime
from enum import Enum

from pydantic import BaseModel, ConfigDict, field_serializer, field_validator


# ---------------------------------------------------------------------------
# Enums
# ---------------------------------------------------------------------------


class PolicyEffect(str, Enum):
    """What happens when a policy rule fires.

    Ordered from least to most restrictive for comparison purposes.
    """
    ALLOW            = "allow"
    WARN             = "warn"
    REDACT           = "redact"
    REQUIRE_APPROVAL = "require_approval"
    DENY             = "deny"
    REQUIRE_LEDGER   = "require_ledger"


class PolicyTrigger(str, Enum):
    """Which pipeline stage evaluates the rule."""
    ON_QUERY      = "on-query"
    ON_RETRIEVAL  = "on-retrieval"
    ON_GENERATION = "on-generation"
    ON_RELEASE    = "on-release"


class PolicyScope(str, Enum):
    """Where the policy applies within the org."""
    ORG_WIDE              = "org_wide"
    ROLE_SPECIFIC         = "role_specific"
    DOCUMENT_TAG_SPECIFIC = "document_tag_specific"


class OrgRole(str, Enum):
    """Least-privilege role hierarchy. Each role implies all roles below it."""
    MEMBER      = "member"
    CONTRIBUTOR = "contributor"
    REVIEWER    = "reviewer"
    AUDITOR     = "auditor"
    ADMIN       = "admin"
    OWNER       = "owner"


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
# Value objects — ledger-recording types (canonical home; re-exported by ledger)
# ---------------------------------------------------------------------------


class PolicyEvaluation(BaseModel):
    """Single policy evaluation outcome recorded inside a ledger entry."""
    model_config = ConfigDict(frozen=True)

    trigger:   PolicyTrigger
    effect:    PolicyEffect
    policy_id: str


class PolicyRecord(BaseModel):
    """Full policy context snapshotted into a ledger decision entry."""
    model_config = ConfigDict(frozen=True)

    snapshot_id:  str
    evaluations:  list[PolicyEvaluation]


# ---------------------------------------------------------------------------
# Value objects — Policy Engine internals
# ---------------------------------------------------------------------------


class PolicyCondition(BaseModel):
    """Conditions that must all hold for a rule to fire.

    Empty lists are unconstrained (match anything for that dimension).
    """
    model_config = ConfigDict(frozen=True)

    matched_tags:    list[str]      = []
    detected_topics: list[str]      = []
    required_role:   OrgRole | None = None
    requires_pii:    bool           = False


class PolicyRule(BaseModel):
    """A single declarative rule: when/what → effect + message."""
    model_config = ConfigDict(frozen=True)

    trigger:   PolicyTrigger
    condition: PolicyCondition
    effect:    PolicyEffect
    message:   str


class PolicyEvaluationContext(BaseModel):
    """Runtime context the engine receives when evaluating at a pipeline seam."""
    model_config = ConfigDict(frozen=True)

    org_id:          str
    actor_uid:       str
    actor_role:      OrgRole
    trigger:         PolicyTrigger
    query:           str | None = None
    document_tags:   list[str]  = []
    detected_topics: list[str]  = []
    pii_detected:    bool       = False


class PolicyDecision(BaseModel):
    """Engine output for one evaluation: the winning rule's decision."""
    model_config = ConfigDict(frozen=True)

    trigger:      PolicyTrigger
    effect:       PolicyEffect
    policy_id:    str | None       # None → default allow (no rule matched)
    snapshot_id:  str
    message:      str
    matched_rule: PolicyRule | None = None


# ---------------------------------------------------------------------------
# Domain models
# ---------------------------------------------------------------------------


class Policy(BaseModel):
    """Versioned policy document stored per org.

    Frozen in Python — edits produce a new version (incremented `version`,
    new `updated_at`), matching the append-preferred Firestore convention.
    """
    model_config = ConfigDict(frozen=True)

    id:           str
    org_id:       str
    name:         str
    description:  str
    scope:        PolicyScope
    # Non-null only when scope is ROLE_SPECIFIC or DOCUMENT_TAG_SPECIFIC.
    scope_target: str | None = None
    rules:        list[PolicyRule]
    is_active:    bool
    version:      int
    created_by:   str
    created_at:   datetime
    updated_at:   datetime

    @field_validator("version")
    @classmethod
    def version_positive(cls, v: int) -> int:
        if v < 1:
            raise ValueError("version must be >= 1")
        return v

    @field_validator("scope_target")
    @classmethod
    def scope_target_not_blank(cls, v: str | None) -> str | None:
        if v is not None and not v.strip():
            raise ValueError("scope_target must not be blank when provided")
        return v

    @field_validator("created_at", "updated_at")
    @classmethod
    def must_be_utc(cls, v: datetime) -> datetime:
        return _require_utc(v)

    @field_serializer("created_at", "updated_at")
    def serialize_dt(self, v: datetime) -> str:
        return v.isoformat().replace("+00:00", "Z")


class PolicySnapshot(BaseModel):
    """Immutable point-in-time bundle of all active policies for an org.

    The ledger references snapshot_id so a later policy edit cannot retroactively
    alter what governed a past decision.
    """
    model_config = ConfigDict(frozen=True)

    id:         str
    org_id:     str
    policies:   list[Policy]
    created_at: datetime
    created_by: str

    @field_validator("created_at")
    @classmethod
    def must_be_utc(cls, v: datetime) -> datetime:
        return _require_utc(v)

    @field_serializer("created_at")
    def serialize_dt(self, v: datetime) -> str:
        return v.isoformat().replace("+00:00", "Z")
