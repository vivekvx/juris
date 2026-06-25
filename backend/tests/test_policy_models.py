"""Unit tests for Policy Engine domain models."""
from __future__ import annotations

from datetime import datetime, timezone, timedelta

import pytest
from pydantic import ValidationError

from app.models.policy import (
    OrgRole,
    Policy,
    PolicyCondition,
    PolicyDecision,
    PolicyEffect,
    PolicyEvaluation,
    PolicyEvaluationContext,
    PolicyRecord,
    PolicyRule,
    PolicyScope,
    PolicySnapshot,
    PolicyTrigger,
)


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

UTC = timezone.utc
_NOW = datetime(2026, 6, 25, 10, 0, 0, tzinfo=UTC)


def _condition(**kw: object) -> PolicyCondition:
    return PolicyCondition(**kw)  # type: ignore[arg-type]


def _rule(**kw: object) -> PolicyRule:
    base: dict[str, object] = dict(
        trigger=PolicyTrigger.ON_RELEASE,
        condition=_condition(),
        effect=PolicyEffect.ALLOW,
        message="Default allow.",
    )
    base.update(kw)
    return PolicyRule(**base)  # type: ignore[arg-type]


def _policy(**kw: object) -> Policy:
    base: dict[str, object] = dict(
        id="pol_001",
        org_id="org_abc",
        name="Default Policy",
        description="Allow everything.",
        scope=PolicyScope.ORG_WIDE,
        scope_target=None,
        rules=[_rule()],
        is_active=True,
        version=1,
        created_by="uid_alice",
        created_at=_NOW,
        updated_at=_NOW,
    )
    base.update(kw)
    return Policy(**base)  # type: ignore[arg-type]


def _snapshot(**kw: object) -> PolicySnapshot:
    base: dict[str, object] = dict(
        id="snap_001",
        org_id="org_abc",
        policies=[_policy()],
        created_at=_NOW,
        created_by="uid_alice",
    )
    base.update(kw)
    return PolicySnapshot(**base)  # type: ignore[arg-type]


# ---------------------------------------------------------------------------
# PolicyEffect
# ---------------------------------------------------------------------------


class TestPolicyEffect:
    def test_all_values(self) -> None:
        assert {e.value for e in PolicyEffect} == {
            "allow", "warn", "redact", "require_approval", "deny", "require_ledger",
        }

    def test_is_str(self) -> None:
        assert isinstance(PolicyEffect.ALLOW, str)

    def test_invalid_value(self) -> None:
        with pytest.raises(ValueError):
            PolicyEffect("explode")  # type: ignore[arg-type]


# ---------------------------------------------------------------------------
# PolicyTrigger
# ---------------------------------------------------------------------------


class TestPolicyTrigger:
    def test_all_values(self) -> None:
        assert {t.value for t in PolicyTrigger} == {
            "on-query", "on-retrieval", "on-generation", "on-release",
        }

    def test_is_str(self) -> None:
        assert isinstance(PolicyTrigger.ON_QUERY, str)

    def test_invalid_value(self) -> None:
        with pytest.raises(ValueError):
            PolicyTrigger("on-something-else")  # type: ignore[arg-type]


# ---------------------------------------------------------------------------
# PolicyScope
# ---------------------------------------------------------------------------


class TestPolicyScope:
    def test_all_values(self) -> None:
        assert {s.value for s in PolicyScope} == {
            "org_wide", "role_specific", "document_tag_specific",
        }

    def test_is_str(self) -> None:
        assert isinstance(PolicyScope.ORG_WIDE, str)

    def test_invalid_value(self) -> None:
        with pytest.raises(ValueError):
            PolicyScope("global")  # type: ignore[arg-type]


# ---------------------------------------------------------------------------
# OrgRole
# ---------------------------------------------------------------------------


class TestOrgRole:
    def test_all_values(self) -> None:
        assert {r.value for r in OrgRole} == {
            "member", "contributor", "reviewer", "auditor", "admin", "owner",
        }

    def test_is_str(self) -> None:
        assert isinstance(OrgRole.OWNER, str)

    def test_invalid_value(self) -> None:
        with pytest.raises(ValueError):
            OrgRole("superuser")  # type: ignore[arg-type]


# ---------------------------------------------------------------------------
# PolicyEvaluation (re-exported from policy, used by ledger)
# ---------------------------------------------------------------------------


class TestPolicyEvaluation:
    def test_valid_construction(self) -> None:
        e = PolicyEvaluation(
            trigger=PolicyTrigger.ON_RELEASE,
            effect=PolicyEffect.ALLOW,
            policy_id="pol_001",
        )
        assert e.trigger == PolicyTrigger.ON_RELEASE
        assert e.effect == PolicyEffect.ALLOW
        assert e.policy_id == "pol_001"

    def test_frozen(self) -> None:
        e = PolicyEvaluation(
            trigger=PolicyTrigger.ON_QUERY,
            effect=PolicyEffect.DENY,
            policy_id="pol_002",
        )
        with pytest.raises(Exception):
            e.policy_id = "other"  # type: ignore[misc]

    def test_invalid_trigger(self) -> None:
        with pytest.raises(ValidationError):
            PolicyEvaluation(trigger="on-something", effect="allow", policy_id="x")  # type: ignore[arg-type]

    def test_invalid_effect(self) -> None:
        with pytest.raises(ValidationError):
            PolicyEvaluation(trigger="on-query", effect="explode", policy_id="x")  # type: ignore[arg-type]


# ---------------------------------------------------------------------------
# PolicyRecord
# ---------------------------------------------------------------------------


class TestPolicyRecord:
    def test_valid_construction(self) -> None:
        pr = PolicyRecord(
            snapshot_id="snap_001",
            evaluations=[
                PolicyEvaluation(
                    trigger=PolicyTrigger.ON_RELEASE,
                    effect=PolicyEffect.ALLOW,
                    policy_id="pol_001",
                )
            ],
        )
        assert pr.snapshot_id == "snap_001"
        assert len(pr.evaluations) == 1

    def test_empty_evaluations(self) -> None:
        pr = PolicyRecord(snapshot_id="snap_001", evaluations=[])
        assert pr.evaluations == []

    def test_frozen(self) -> None:
        pr = PolicyRecord(snapshot_id="snap_001", evaluations=[])
        with pytest.raises(Exception):
            pr.snapshot_id = "other"  # type: ignore[misc]


# ---------------------------------------------------------------------------
# PolicyCondition
# ---------------------------------------------------------------------------


class TestPolicyCondition:
    def test_defaults(self) -> None:
        c = PolicyCondition()
        assert c.matched_tags == []
        assert c.detected_topics == []
        assert c.required_role is None
        assert c.requires_pii is False

    def test_with_all_fields(self) -> None:
        c = PolicyCondition(
            matched_tags=["confidential"],
            detected_topics=["litigation hold"],
            required_role=OrgRole.REVIEWER,
            requires_pii=True,
        )
        assert c.matched_tags == ["confidential"]
        assert c.required_role == OrgRole.REVIEWER
        assert c.requires_pii is True

    def test_frozen(self) -> None:
        c = PolicyCondition()
        with pytest.raises(Exception):
            c.requires_pii = True  # type: ignore[misc]

    def test_invalid_role(self) -> None:
        with pytest.raises(ValidationError):
            PolicyCondition(required_role="superuser")  # type: ignore[arg-type]

    def test_empty_lists_default(self) -> None:
        c = PolicyCondition(matched_tags=["pii"])
        assert c.detected_topics == []


# ---------------------------------------------------------------------------
# PolicyRule
# ---------------------------------------------------------------------------


class TestPolicyRule:
    def test_valid_construction(self) -> None:
        r = _rule()
        assert r.trigger == PolicyTrigger.ON_RELEASE
        assert r.effect == PolicyEffect.ALLOW
        assert r.message == "Default allow."

    def test_frozen(self) -> None:
        r = _rule()
        with pytest.raises(Exception):
            r.message = "changed"  # type: ignore[misc]

    def test_all_effects_accepted(self) -> None:
        for effect in PolicyEffect:
            r = _rule(effect=effect, message=f"Effect: {effect.value}")
            assert r.effect == effect

    def test_all_triggers_accepted(self) -> None:
        for trigger in PolicyTrigger:
            r = _rule(trigger=trigger)
            assert r.trigger == trigger

    def test_invalid_effect(self) -> None:
        with pytest.raises(ValidationError):
            _rule(effect="nuclear")

    def test_invalid_trigger(self) -> None:
        with pytest.raises(ValidationError):
            _rule(trigger="on-something")

    def test_condition_embedded(self) -> None:
        r = _rule(condition=_condition(requires_pii=True))
        assert r.condition.requires_pii is True

    def test_deny_with_condition(self) -> None:
        r = _rule(
            trigger=PolicyTrigger.ON_QUERY,
            condition=_condition(detected_topics=["litigation hold"]),
            effect=PolicyEffect.DENY,
            message="Litigation hold: query blocked.",
        )
        assert r.effect == PolicyEffect.DENY
        assert "litigation hold" in r.condition.detected_topics


# ---------------------------------------------------------------------------
# PolicyEvaluationContext
# ---------------------------------------------------------------------------


class TestPolicyEvaluationContext:
    def test_minimal_construction(self) -> None:
        ctx = PolicyEvaluationContext(
            org_id="org_abc",
            actor_uid="uid_alice",
            actor_role=OrgRole.MEMBER,
            trigger=PolicyTrigger.ON_QUERY,
        )
        assert ctx.query is None
        assert ctx.document_tags == []
        assert ctx.pii_detected is False

    def test_with_all_fields(self) -> None:
        ctx = PolicyEvaluationContext(
            org_id="org_abc",
            actor_uid="uid_alice",
            actor_role=OrgRole.ADMIN,
            trigger=PolicyTrigger.ON_RETRIEVAL,
            query="Can we cap liability?",
            document_tags=["confidential", "litigation"],
            detected_topics=["litigation hold"],
            pii_detected=True,
        )
        assert ctx.query == "Can we cap liability?"
        assert "confidential" in ctx.document_tags
        assert ctx.pii_detected is True

    def test_frozen(self) -> None:
        ctx = PolicyEvaluationContext(
            org_id="org_abc",
            actor_uid="uid_alice",
            actor_role=OrgRole.MEMBER,
            trigger=PolicyTrigger.ON_QUERY,
        )
        with pytest.raises(Exception):
            ctx.pii_detected = True  # type: ignore[misc]

    def test_invalid_role(self) -> None:
        with pytest.raises(ValidationError):
            PolicyEvaluationContext(
                org_id="org_abc",
                actor_uid="uid_alice",
                actor_role="god",  # type: ignore[arg-type]
                trigger=PolicyTrigger.ON_QUERY,
            )

    def test_invalid_trigger(self) -> None:
        with pytest.raises(ValidationError):
            PolicyEvaluationContext(
                org_id="org_abc",
                actor_uid="uid_alice",
                actor_role=OrgRole.MEMBER,
                trigger="on-something",  # type: ignore[arg-type]
            )


# ---------------------------------------------------------------------------
# PolicyDecision
# ---------------------------------------------------------------------------


class TestPolicyDecision:
    def test_default_allow(self) -> None:
        d = PolicyDecision(
            trigger=PolicyTrigger.ON_RELEASE,
            effect=PolicyEffect.ALLOW,
            policy_id=None,
            snapshot_id="snap_001",
            message="No rule matched; default allow.",
        )
        assert d.policy_id is None
        assert d.matched_rule is None
        assert d.effect == PolicyEffect.ALLOW

    def test_matched_rule(self) -> None:
        rule = _rule(effect=PolicyEffect.DENY, message="Litigation hold active.")
        d = PolicyDecision(
            trigger=PolicyTrigger.ON_QUERY,
            effect=PolicyEffect.DENY,
            policy_id="pol_001",
            snapshot_id="snap_001",
            message="Litigation hold active.",
            matched_rule=rule,
        )
        assert d.matched_rule is not None
        assert d.matched_rule.effect == PolicyEffect.DENY

    def test_frozen(self) -> None:
        d = PolicyDecision(
            trigger=PolicyTrigger.ON_RELEASE,
            effect=PolicyEffect.ALLOW,
            policy_id=None,
            snapshot_id="snap_001",
            message="ok",
        )
        with pytest.raises(Exception):
            d.effect = PolicyEffect.DENY  # type: ignore[misc]

    def test_all_effects_representable(self) -> None:
        for effect in PolicyEffect:
            d = PolicyDecision(
                trigger=PolicyTrigger.ON_RELEASE,
                effect=effect,
                policy_id="pol_001",
                snapshot_id="snap_001",
                message=f"Effect: {effect.value}",
            )
            assert d.effect == effect


# ---------------------------------------------------------------------------
# Policy
# ---------------------------------------------------------------------------


class TestPolicy:
    def test_valid_construction(self) -> None:
        p = _policy()
        assert p.id == "pol_001"
        assert p.scope == PolicyScope.ORG_WIDE
        assert p.version == 1
        assert p.is_active is True

    def test_frozen(self) -> None:
        p = _policy()
        with pytest.raises(Exception):
            p.name = "changed"  # type: ignore[misc]

    def test_naive_created_at_rejected(self) -> None:
        with pytest.raises(ValidationError):
            _policy(created_at=datetime(2026, 6, 25, 10, 0, 0))

    def test_naive_updated_at_rejected(self) -> None:
        with pytest.raises(ValidationError):
            _policy(updated_at=datetime(2026, 6, 25, 10, 0, 0))

    def test_non_utc_rejected(self) -> None:
        eastern = datetime(2026, 6, 25, 10, 0, 0, tzinfo=timezone(timedelta(hours=-5)))
        with pytest.raises(ValidationError):
            _policy(created_at=eastern)

    def test_serialization_z_suffix(self) -> None:
        p = _policy()
        data = p.model_dump(mode="json")
        assert data["created_at"].endswith("Z")
        assert data["updated_at"].endswith("Z")

    def test_version_zero_rejected(self) -> None:
        with pytest.raises(ValidationError):
            _policy(version=0)

    def test_version_negative_rejected(self) -> None:
        with pytest.raises(ValidationError):
            _policy(version=-1)

    def test_version_increments_accepted(self) -> None:
        p = _policy(version=42)
        assert p.version == 42

    def test_empty_rules_allowed(self) -> None:
        p = _policy(rules=[])
        assert p.rules == []

    def test_scope_target_blank_rejected(self) -> None:
        with pytest.raises(ValidationError):
            _policy(scope_target="   ")

    def test_scope_target_present(self) -> None:
        p = _policy(scope=PolicyScope.ROLE_SPECIFIC, scope_target="reviewer")
        assert p.scope_target == "reviewer"

    def test_document_tag_scope(self) -> None:
        p = _policy(
            scope=PolicyScope.DOCUMENT_TAG_SPECIFIC,
            scope_target="confidential",
        )
        assert p.scope == PolicyScope.DOCUMENT_TAG_SPECIFIC
        assert p.scope_target == "confidential"

    def test_multiple_rules(self) -> None:
        rules = [
            _rule(trigger=PolicyTrigger.ON_QUERY, effect=PolicyEffect.DENY, message="Denied."),
            _rule(trigger=PolicyTrigger.ON_RELEASE, effect=PolicyEffect.WARN, message="Warned."),
        ]
        p = _policy(rules=rules)
        assert len(p.rules) == 2

    def test_inactive_policy(self) -> None:
        p = _policy(is_active=False)
        assert p.is_active is False

    def test_scope_enum_serialization(self) -> None:
        p = _policy()
        data = p.model_dump(mode="json")
        assert data["scope"] == "org_wide"


# ---------------------------------------------------------------------------
# PolicySnapshot
# ---------------------------------------------------------------------------


class TestPolicySnapshot:
    def test_valid_construction(self) -> None:
        s = _snapshot()
        assert s.id == "snap_001"
        assert s.org_id == "org_abc"
        assert len(s.policies) == 1

    def test_frozen(self) -> None:
        s = _snapshot()
        with pytest.raises(Exception):
            s.id = "other"  # type: ignore[misc]

    def test_empty_policies_allowed(self) -> None:
        s = _snapshot(policies=[])
        assert s.policies == []

    def test_naive_timestamp_rejected(self) -> None:
        with pytest.raises(ValidationError):
            _snapshot(created_at=datetime(2026, 6, 25, 10, 0, 0))

    def test_non_utc_rejected(self) -> None:
        eastern = datetime(2026, 6, 25, 10, 0, 0, tzinfo=timezone(timedelta(hours=-5)))
        with pytest.raises(ValidationError):
            _snapshot(created_at=eastern)

    def test_serialization_z_suffix(self) -> None:
        s = _snapshot()
        data = s.model_dump(mode="json")
        assert data["created_at"].endswith("Z")

    def test_multiple_policies(self) -> None:
        p2 = _policy(id="pol_002", name="Strict Policy", version=2)
        s = _snapshot(policies=[_policy(), p2])
        assert len(s.policies) == 2

    def test_nested_policy_serialization(self) -> None:
        s = _snapshot()
        data = s.model_dump(mode="json")
        pol = data["policies"][0]
        assert pol["created_at"].endswith("Z")
        assert pol["scope"] == "org_wide"

    def test_snapshot_captures_policy_at_moment(self) -> None:
        p = _policy(version=3, is_active=True)
        s = _snapshot(policies=[p])
        assert s.policies[0].version == 3


# ---------------------------------------------------------------------------
# Re-export consistency: ledger imports still resolve to same objects
# ---------------------------------------------------------------------------


class TestLedgerReExport:
    def test_policy_effect_same_object(self) -> None:
        from app.models.ledger import PolicyEffect as LedgerEffect
        from app.models.policy import PolicyEffect as PolicyEff
        assert LedgerEffect is PolicyEff

    def test_policy_trigger_same_object(self) -> None:
        from app.models.ledger import PolicyTrigger as LedgerTrigger
        from app.models.policy import PolicyTrigger as PolicyTrig
        assert LedgerTrigger is PolicyTrig

    def test_policy_evaluation_same_object(self) -> None:
        from app.models.ledger import PolicyEvaluation as LE
        from app.models.policy import PolicyEvaluation as PE
        assert LE is PE

    def test_policy_record_same_object(self) -> None:
        from app.models.ledger import PolicyRecord as LR
        from app.models.policy import PolicyRecord as PR
        assert LR is PR
