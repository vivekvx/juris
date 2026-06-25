"""Unit tests for AI Decision Ledger domain models — no mocks, no network, no Firestore."""
from __future__ import annotations

import json
from datetime import datetime, timedelta, timezone

import pytest
from pydantic import ValidationError

from app.models.ledger import (
    CachedCitation,
    DecisionAnnotation,
    DecisionEvent,
    DecisionKind,
    GroundingStatus,
    HumanOverride,
    MemoryRef,
    ModelParams,
    OutputRecord,
    OverrideDisposition,
    PolicyEffect,
    PolicyEvaluation,
    PolicyRecord,
    PolicyTrigger,
    RetrievalParams,
    RetrievalRecord,
)

UTC = timezone.utc
_T0 = datetime(2026, 6, 25, 6, 30, 0, tzinfo=UTC)
_HASH_A = "sha256:aabbccddeeff00112233445566778899aabbccddeeff00112233445566778899"
_HASH_B = "sha256:0011223344556677889900aabbccddeeff0011223344556677889900aabbccdd"


# ---------------------------------------------------------------------------
# Helpers to build minimal valid instances
# ---------------------------------------------------------------------------


def _citation(**kw: object) -> CachedCitation:
    base: dict[str, object] = dict(
        doc_id="doc_001",
        chunk_index=4,
        page_number=12,
        score=0.71,
        original_filename="MSA.pdf",
    )
    base.update(kw)
    return CachedCitation(**base)  # type: ignore[arg-type]


def _retrieval(**kw: object) -> RetrievalRecord:
    base: dict[str, object] = dict(
        params=RetrievalParams(top_k=5, score_threshold=0.3),
        citations=[_citation()],
    )
    base.update(kw)
    return RetrievalRecord(**base)  # type: ignore[arg-type]


def _model_params(**kw: object) -> ModelParams:
    base: dict[str, object] = dict(
        name="gemini-2.5-flash",
        temperature=0.3,
        max_output_tokens=2048,
        prompt_template_version="m6.1",
    )
    base.update(kw)
    return ModelParams(**base)  # type: ignore[arg-type]


def _policy(**kw: object) -> PolicyRecord:
    base: dict[str, object] = dict(
        snapshot_id="snap_001",
        evaluations=[
            PolicyEvaluation(
                trigger=PolicyTrigger.ON_RELEASE,
                effect=PolicyEffect.ALLOW,
                policy_id="pol_001",
            )
        ],
    )
    base.update(kw)
    return PolicyRecord(**base)  # type: ignore[arg-type]


def _grounding(**kw: object) -> GroundingStatus:
    base: dict[str, object] = dict(
        citations_above_threshold=3,
        top_score=0.71,
        disclaimer_emitted=False,
    )
    base.update(kw)
    return GroundingStatus(**base)  # type: ignore[arg-type]


def _output(**kw: object) -> OutputRecord:
    base: dict[str, object] = dict(
        answer_hash=_HASH_A,
        answer_ref="msg_asst_001",
        sources_used=True,
        grounding=_grounding(),
    )
    base.update(kw)
    return OutputRecord(**base)  # type: ignore[arg-type]


def _decision(**kw: object) -> DecisionEvent:
    base: dict[str, object] = dict(
        id="entry_001",
        org_id="org_abc",
        kind=DecisionKind.DECISION,
        sequence_no=1,
        actor_uid="uid_alice",
        conversation_id="conv_001",
        message_id="msg_asst_001",
        query="Can we cap liability at 6 months?",
        document_ids=["doc_001"],
        retrieval=_retrieval(),
        memory_used=[],
        model=_model_params(),
        policy=_policy(),
        output=_output(),
        prev_hash=_HASH_B,
        entry_hash=_HASH_A,
        created_at=_T0,
    )
    base.update(kw)
    return DecisionEvent(**base)  # type: ignore[arg-type]


def _override(**kw: object) -> HumanOverride:
    base: dict[str, object] = dict(
        id="entry_002",
        org_id="org_abc",
        kind=DecisionKind.OVERRIDE,
        sequence_no=2,
        actor_uid="uid_bob",
        conversation_id="conv_001",
        decision_id="entry_001",
        approver="uid_bob",
        reason="Client confirmed 12-month cap is standard.",
        previous_recommendation=_HASH_A,
        final_outcome="Liability cap set at 12 months per org standard.",
        disposition=OverrideDisposition.REPLACED,
        prev_hash=_HASH_A,
        entry_hash=_HASH_B,
        created_at=_T0,
    )
    base.update(kw)
    return HumanOverride(**base)  # type: ignore[arg-type]


def _annotation(**kw: object) -> DecisionAnnotation:
    base: dict[str, object] = dict(
        id="entry_003",
        org_id="org_abc",
        kind=DecisionKind.ANNOTATION,
        sequence_no=3,
        actor_uid="uid_alice",
        conversation_id="conv_001",
        decision_id="entry_001",
        original_hash=_HASH_A,
        note="Subsequent review confirmed the cited clause is version 3, not version 2.",
        prev_hash=_HASH_B,
        entry_hash="sha256:ccddee",
        created_at=_T0,
    )
    base.update(kw)
    return DecisionAnnotation(**base)  # type: ignore[arg-type]


# ===========================================================================
# DecisionKind
# ===========================================================================


class TestDecisionKind:
    def test_values(self) -> None:
        assert DecisionKind.DECISION.value == "decision"
        assert DecisionKind.ANNOTATION.value == "annotation"
        assert DecisionKind.OVERRIDE.value == "override"

    def test_exactly_three_members(self) -> None:
        assert {k.value for k in DecisionKind} == {"decision", "annotation", "override"}

    def test_is_string_subtype(self) -> None:
        assert isinstance(DecisionKind.DECISION, str)

    def test_from_string(self) -> None:
        assert DecisionKind("decision") is DecisionKind.DECISION

    def test_invalid_value_raises(self) -> None:
        with pytest.raises(ValueError):
            DecisionKind("unknown")


# ===========================================================================
# PolicyEffect
# ===========================================================================


class TestPolicyEffect:
    def test_all_values(self) -> None:
        assert {e.value for e in PolicyEffect} == {
            "allow", "warn", "redact", "require_approval", "deny", "require_ledger"
        }

    def test_is_string_subtype(self) -> None:
        assert isinstance(PolicyEffect.ALLOW, str)


# ===========================================================================
# PolicyTrigger
# ===========================================================================


class TestPolicyTrigger:
    def test_all_values(self) -> None:
        assert {t.value for t in PolicyTrigger} == {
            "on-query", "on-retrieval", "on-generation", "on-release"
        }

    def test_is_string_subtype(self) -> None:
        assert isinstance(PolicyTrigger.ON_QUERY, str)


# ===========================================================================
# OverrideDisposition
# ===========================================================================


class TestOverrideDisposition:
    def test_all_values(self) -> None:
        assert {d.value for d in OverrideDisposition} == {"rejected", "replaced", "amended"}

    def test_is_string_subtype(self) -> None:
        assert isinstance(OverrideDisposition.REJECTED, str)


# ===========================================================================
# GroundingStatus
# ===========================================================================


class TestGroundingStatus:
    def test_construction(self) -> None:
        g = _grounding()
        assert g.citations_above_threshold == 3
        assert g.top_score == 0.71
        assert g.disclaimer_emitted is False

    def test_frozen(self) -> None:
        g = _grounding()
        with pytest.raises((ValidationError, TypeError)):
            g.top_score = 0.99
    def test_zero_citations(self) -> None:
        g = _grounding(citations_above_threshold=0, top_score=0.0)
        assert g.citations_above_threshold == 0

    def test_disclaimer_emitted_true(self) -> None:
        g = _grounding(disclaimer_emitted=True)
        assert g.disclaimer_emitted is True

    def test_invalid_top_score_type(self) -> None:
        with pytest.raises(ValidationError):
            _grounding(top_score="high")


# ===========================================================================
# CachedCitation
# ===========================================================================


class TestCachedCitation:
    def test_construction(self) -> None:
        c = _citation()
        assert c.doc_id == "doc_001"
        assert c.chunk_index == 4
        assert c.page_number == 12
        assert c.score == 0.71
        assert c.original_filename == "MSA.pdf"

    def test_page_number_none(self) -> None:
        c = _citation(page_number=None)
        assert c.page_number is None

    def test_frozen(self) -> None:
        c = _citation()
        with pytest.raises((ValidationError, TypeError)):
            c.score = 0.99
    def test_invalid_score_type(self) -> None:
        with pytest.raises(ValidationError):
            _citation(score="high")


# ===========================================================================
# RetrievalRecord
# ===========================================================================


class TestRetrievalRecord:
    def test_construction(self) -> None:
        r = _retrieval()
        assert r.params.top_k == 5
        assert r.params.score_threshold == 0.3
        assert len(r.citations) == 1

    def test_empty_citations_allowed(self) -> None:
        r = _retrieval(citations=[])
        assert r.citations == []

    def test_frozen(self) -> None:
        r = _retrieval()
        with pytest.raises((ValidationError, TypeError)):
            r.citations = []
    def test_multiple_citations(self) -> None:
        r = _retrieval(citations=[_citation(), _citation(chunk_index=5)])
        assert len(r.citations) == 2


# ===========================================================================
# MemoryRef
# ===========================================================================


class TestMemoryRef:
    def test_construction(self) -> None:
        m = MemoryRef(entry_id="mem_001", version=3, kind="precedent")
        assert m.entry_id == "mem_001"
        assert m.version == 3
        assert m.kind == "precedent"

    def test_frozen(self) -> None:
        m = MemoryRef(entry_id="mem_001", version=1, kind="clause")
        with pytest.raises((ValidationError, TypeError)):
            m.version = 2

# ===========================================================================
# PolicyEvaluation
# ===========================================================================


class TestPolicyEvaluation:
    def test_construction(self) -> None:
        e = PolicyEvaluation(
            trigger=PolicyTrigger.ON_RELEASE,
            effect=PolicyEffect.ALLOW,
            policy_id="pol_001",
        )
        assert e.trigger == PolicyTrigger.ON_RELEASE
        assert e.effect == PolicyEffect.ALLOW

    def test_from_strings(self) -> None:
        e = PolicyEvaluation(
            trigger="on-query",  # type: ignore[arg-type]
            effect="deny",  # type: ignore[arg-type]
            policy_id="pol_002",
        )
        assert e.trigger == PolicyTrigger.ON_QUERY
        assert e.effect == PolicyEffect.DENY

    def test_invalid_trigger_rejected(self) -> None:
        with pytest.raises(ValidationError):
            PolicyEvaluation(trigger="on-something", effect="allow", policy_id="x")  # type: ignore[arg-type]

    def test_invalid_effect_rejected(self) -> None:
        with pytest.raises(ValidationError):
            PolicyEvaluation(trigger="on-query", effect="explode", policy_id="x")  # type: ignore[arg-type]


# ===========================================================================
# DecisionEvent
# ===========================================================================


class TestDecisionEvent:
    def test_construction(self) -> None:
        d = _decision()
        assert d.id == "entry_001"
        assert d.org_id == "org_abc"
        assert d.kind == DecisionKind.DECISION
        assert d.sequence_no == 1

    def test_all_fields_present(self) -> None:
        keys = set(_decision().model_dump().keys())
        assert keys == {
            "id", "org_id", "kind", "sequence_no", "actor_uid",
            "conversation_id", "message_id", "query", "document_ids",
            "language", "retrieval", "memory_used", "model", "policy",
            "output", "prev_hash", "entry_hash", "created_at",
        }

    def test_language_optional_default_none(self) -> None:
        d = _decision()
        assert d.language is None

    def test_language_set(self) -> None:
        d = _decision(language="en")
        assert d.language == "en"

    def test_empty_document_ids(self) -> None:
        d = _decision(document_ids=[])
        assert d.document_ids == []

    def test_multiple_document_ids(self) -> None:
        d = _decision(document_ids=["doc_001", "doc_002"])
        assert len(d.document_ids) == 2

    def test_memory_used_populated(self) -> None:
        ref = MemoryRef(entry_id="mem_001", version=3, kind="precedent")
        d = _decision(memory_used=[ref])
        assert len(d.memory_used) == 1
        assert d.memory_used[0].entry_id == "mem_001"

    def test_frozen(self) -> None:
        d = _decision()
        with pytest.raises((ValidationError, TypeError)):
            d.query = "new query"
    def test_frozen_entry_hash(self) -> None:
        d = _decision()
        with pytest.raises((ValidationError, TypeError)):
            d.entry_hash = "sha256:tampered"
    def test_sequence_no_zero_allowed(self) -> None:
        d = _decision(sequence_no=0)
        assert d.sequence_no == 0

    def test_large_sequence_no(self) -> None:
        d = _decision(sequence_no=999_999)
        assert d.sequence_no == 999_999

    # --- UTC validation ---

    def test_naive_created_at_rejected(self) -> None:
        with pytest.raises(ValidationError, match="timezone-aware"):
            _decision(created_at=datetime(2026, 1, 1))

    def test_non_utc_timezone_rejected(self) -> None:
        ist = timezone(timedelta(hours=5, minutes=30))
        with pytest.raises(ValidationError, match="UTC"):
            _decision(created_at=datetime(2026, 1, 1, 12, 0, 0, tzinfo=ist))

    def test_negative_offset_rejected(self) -> None:
        est = timezone(timedelta(hours=-5))
        with pytest.raises(ValidationError, match="UTC"):
            _decision(created_at=datetime(2026, 1, 1, 12, 0, 0, tzinfo=est))

    # --- Serialization ---

    def test_json_is_valid(self) -> None:
        parsed = json.loads(_decision().model_dump_json())
        assert parsed["id"] == "entry_001"

    def test_created_at_serializes_z(self) -> None:
        parsed = json.loads(_decision().model_dump_json())
        assert parsed["created_at"].endswith("Z")
        assert "+00:00" not in parsed["created_at"]

    def test_timestamp_exact_format(self) -> None:
        d = _decision(created_at=datetime(2026, 6, 25, 6, 30, 0, tzinfo=UTC))
        parsed = json.loads(d.model_dump_json())
        assert parsed["created_at"] == "2026-06-25T06:30:00Z"

    def test_kind_serializes_as_string(self) -> None:
        parsed = json.loads(_decision().model_dump_json())
        assert parsed["kind"] == "decision"

    def test_nested_effect_serializes_as_string(self) -> None:
        parsed = json.loads(_decision().model_dump_json())
        effect = parsed["policy"]["evaluations"][0]["effect"]
        assert effect == "allow"

    def test_model_copy_does_not_mutate_original(self) -> None:
        d = _decision()
        updated = d.model_copy(update={"sequence_no": 99})
        assert d.sequence_no == 1
        assert updated.sequence_no == 99

    # --- Edge cases ---

    def test_missing_required_field_rejected(self) -> None:
        with pytest.raises(ValidationError):
            DecisionEvent(  # type: ignore[call-arg]
                id="e", org_id="o", kind=DecisionKind.DECISION,
                sequence_no=1, actor_uid="u", conversation_id="c",
                message_id="m", query="q",
                # document_ids intentionally omitted
                retrieval=_retrieval(), memory_used=[], model=_model_params(),
                policy=_policy(), output=_output(),
                prev_hash=_HASH_A, entry_hash=_HASH_B, created_at=_T0,
            )


# ===========================================================================
# HumanOverride
# ===========================================================================


class TestHumanOverride:
    def test_construction(self) -> None:
        o = _override()
        assert o.id == "entry_002"
        assert o.kind == DecisionKind.OVERRIDE
        assert o.disposition == OverrideDisposition.REPLACED
        assert o.decision_id == "entry_001"

    def test_wrong_kind_rejected(self) -> None:
        with pytest.raises(ValidationError, match="override"):
            _override(kind=DecisionKind.DECISION)

    def test_annotation_kind_rejected(self) -> None:
        with pytest.raises(ValidationError, match="override"):
            _override(kind=DecisionKind.ANNOTATION)

    def test_all_dispositions(self) -> None:
        for disp in OverrideDisposition:
            o = _override(disposition=disp)
            assert o.disposition == disp

    def test_disposition_from_string(self) -> None:
        o = _override(disposition="amended")
        assert o.disposition == OverrideDisposition.AMENDED

    def test_invalid_disposition_rejected(self) -> None:
        with pytest.raises(ValidationError):
            _override(disposition="ignored")

    def test_frozen(self) -> None:
        o = _override()
        with pytest.raises((ValidationError, TypeError)):
            o.reason = "changed reason"
    def test_frozen_entry_hash(self) -> None:
        o = _override()
        with pytest.raises((ValidationError, TypeError)):
            o.entry_hash = "sha256:tampered"
    def test_naive_created_at_rejected(self) -> None:
        with pytest.raises(ValidationError, match="timezone-aware"):
            _override(created_at=datetime(2026, 1, 1))

    def test_non_utc_rejected(self) -> None:
        ist = timezone(timedelta(hours=5, minutes=30))
        with pytest.raises(ValidationError, match="UTC"):
            _override(created_at=datetime(2026, 1, 1, 12, 0, 0, tzinfo=ist))

    def test_created_at_serializes_z(self) -> None:
        parsed = json.loads(_override().model_dump_json())
        assert parsed["created_at"].endswith("Z")

    def test_timestamp_exact_format(self) -> None:
        o = _override(created_at=datetime(2026, 6, 25, 6, 30, 0, tzinfo=UTC))
        parsed = json.loads(o.model_dump_json())
        assert parsed["created_at"] == "2026-06-25T06:30:00Z"

    def test_kind_serializes_as_string(self) -> None:
        parsed = json.loads(_override().model_dump_json())
        assert parsed["kind"] == "override"

    def test_all_fields_present(self) -> None:
        keys = set(_override().model_dump().keys())
        assert keys == {
            "id", "org_id", "kind", "sequence_no", "actor_uid",
            "conversation_id", "decision_id", "approver", "reason",
            "previous_recommendation", "final_outcome", "disposition",
            "prev_hash", "entry_hash", "created_at",
        }

    def test_model_copy_does_not_mutate(self) -> None:
        o = _override()
        updated = o.model_copy(update={"reason": "new reason"})
        assert o.reason == "Client confirmed 12-month cap is standard."
        assert updated.reason == "new reason"


# ===========================================================================
# DecisionAnnotation
# ===========================================================================


class TestDecisionAnnotation:
    def test_construction(self) -> None:
        a = _annotation()
        assert a.id == "entry_003"
        assert a.kind == DecisionKind.ANNOTATION
        assert a.decision_id == "entry_001"
        assert a.original_hash == _HASH_A

    def test_wrong_kind_rejected(self) -> None:
        with pytest.raises(ValidationError, match="annotation"):
            _annotation(kind=DecisionKind.DECISION)

    def test_override_kind_rejected(self) -> None:
        with pytest.raises(ValidationError, match="annotation"):
            _annotation(kind=DecisionKind.OVERRIDE)

    def test_frozen(self) -> None:
        a = _annotation()
        with pytest.raises((ValidationError, TypeError)):
            a.note = "changed note"
    def test_frozen_original_hash(self) -> None:
        a = _annotation()
        with pytest.raises((ValidationError, TypeError)):
            a.original_hash = "sha256:tampered"
    def test_naive_created_at_rejected(self) -> None:
        with pytest.raises(ValidationError, match="timezone-aware"):
            _annotation(created_at=datetime(2026, 1, 1))

    def test_non_utc_rejected(self) -> None:
        jst = timezone(timedelta(hours=9))
        with pytest.raises(ValidationError, match="UTC"):
            _annotation(created_at=datetime(2026, 1, 1, 12, 0, 0, tzinfo=jst))

    def test_created_at_serializes_z(self) -> None:
        parsed = json.loads(_annotation().model_dump_json())
        assert parsed["created_at"].endswith("Z")

    def test_timestamp_exact_format(self) -> None:
        a = _annotation(created_at=datetime(2026, 6, 25, 6, 30, 0, tzinfo=UTC))
        parsed = json.loads(a.model_dump_json())
        assert parsed["created_at"] == "2026-06-25T06:30:00Z"

    def test_kind_serializes_as_string(self) -> None:
        parsed = json.loads(_annotation().model_dump_json())
        assert parsed["kind"] == "annotation"

    def test_all_fields_present(self) -> None:
        keys = set(_annotation().model_dump().keys())
        assert keys == {
            "id", "org_id", "kind", "sequence_no", "actor_uid",
            "conversation_id", "decision_id", "original_hash",
            "note", "prev_hash", "entry_hash", "created_at",
        }

    def test_model_copy_does_not_mutate(self) -> None:
        a = _annotation()
        updated = a.model_copy(update={"note": "revised note"})
        assert "version 3" in a.note
        assert updated.note == "revised note"


# ===========================================================================
# Cross-model: immutability contract across all three entry types
# ===========================================================================


class TestImmutabilityContract:
    """All three entry types share the frozen + hash fields contract."""

    def test_decision_entry_hash_immutable(self) -> None:
        d = _decision()
        with pytest.raises((ValidationError, TypeError)):
            d.entry_hash = "sha256:x"
    def test_override_entry_hash_immutable(self) -> None:
        o = _override()
        with pytest.raises((ValidationError, TypeError)):
            o.entry_hash = "sha256:x"
    def test_annotation_entry_hash_immutable(self) -> None:
        a = _annotation()
        with pytest.raises((ValidationError, TypeError)):
            a.entry_hash = "sha256:x"
    def test_decision_prev_hash_immutable(self) -> None:
        d = _decision()
        with pytest.raises((ValidationError, TypeError)):
            d.prev_hash = "sha256:x"
    def test_override_prev_hash_immutable(self) -> None:
        o = _override()
        with pytest.raises((ValidationError, TypeError)):
            o.prev_hash = "sha256:x"
    def test_annotation_prev_hash_immutable(self) -> None:
        a = _annotation()
        with pytest.raises((ValidationError, TypeError)):
            a.prev_hash = "sha256:x"