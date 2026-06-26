"""Unit tests for Policy Engine evaluation service — no I/O, fully deterministic."""
from __future__ import annotations

from datetime import datetime, timezone

import pytest

from app.models.policy import (
    OrgRole,
    Policy,
    PolicyCondition,
    PolicyEffect,
    PolicyEvaluationContext,
    PolicyRule,
    PolicyScope,
    PolicySnapshot,
    PolicyTrigger,
)
from app.services.policy import (
    _DEFAULT_MESSAGE,
    _DEFAULT_SNAPSHOT_ID,
    _EFFECT_PRECEDENCE,
    _ROLE_RANK,
    create_snapshot,
    default_snapshot,
    evaluate,
)

UTC = timezone.utc
_NOW = datetime(2026, 6, 25, 10, 0, 0, tzinfo=UTC)
_ORG = "org_abc"
_UID = "uid_alice"


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _cond(**kw: object) -> PolicyCondition:
    return PolicyCondition(**kw)  # type: ignore[arg-type]


def _rule(
    trigger: PolicyTrigger = PolicyTrigger.ON_RELEASE,
    effect: PolicyEffect = PolicyEffect.ALLOW,
    message: str = "ok",
    **kw: object,
) -> PolicyRule:
    return PolicyRule(
        trigger=trigger,
        condition=_cond(**kw),
        effect=effect,
        message=message,
    )


def _policy(
    rules: list[PolicyRule],
    *,
    pid: str = "pol_001",
    scope: PolicyScope = PolicyScope.ORG_WIDE,
    scope_target: str | None = None,
    is_active: bool = True,
    version: int = 1,
) -> Policy:
    return Policy(
        id=pid,
        org_id=_ORG,
        name="Test Policy",
        description="",
        scope=scope,
        scope_target=scope_target,
        rules=rules,
        is_active=is_active,
        version=version,
        created_by=_UID,
        created_at=_NOW,
        updated_at=_NOW,
    )


def _snap(policies: list[Policy], snap_id: str = "snap_001") -> PolicySnapshot:
    return PolicySnapshot(
        id=snap_id,
        org_id=_ORG,
        policies=policies,
        created_at=_NOW,
        created_by=_UID,
    )


def _ctx(
    trigger: PolicyTrigger = PolicyTrigger.ON_RELEASE,
    role: OrgRole = OrgRole.MEMBER,
    document_tags: list[str] | None = None,
    detected_topics: list[str] | None = None,
    pii_detected: bool = False,
    query: str | None = None,
) -> PolicyEvaluationContext:
    return PolicyEvaluationContext(
        org_id=_ORG,
        actor_uid=_UID,
        actor_role=role,
        trigger=trigger,
        query=query,
        document_tags=document_tags or [],
        detected_topics=detected_topics or [],
        pii_detected=pii_detected,
    )


# ---------------------------------------------------------------------------
# Effect precedence constants
# ---------------------------------------------------------------------------


class TestEffectPrecedence:
    def test_deny_highest(self) -> None:
        assert _EFFECT_PRECEDENCE[PolicyEffect.DENY] == max(_EFFECT_PRECEDENCE.values())

    def test_allow_lowest(self) -> None:
        assert _EFFECT_PRECEDENCE[PolicyEffect.ALLOW] == min(_EFFECT_PRECEDENCE.values())

    def test_all_effects_covered(self) -> None:
        assert set(_EFFECT_PRECEDENCE.keys()) == set(PolicyEffect)

    def test_deny_gt_require_approval(self) -> None:
        assert _EFFECT_PRECEDENCE[PolicyEffect.DENY] > _EFFECT_PRECEDENCE[PolicyEffect.REQUIRE_APPROVAL]

    def test_require_approval_gt_redact(self) -> None:
        assert _EFFECT_PRECEDENCE[PolicyEffect.REQUIRE_APPROVAL] > _EFFECT_PRECEDENCE[PolicyEffect.REDACT]

    def test_redact_gt_warn(self) -> None:
        assert _EFFECT_PRECEDENCE[PolicyEffect.REDACT] > _EFFECT_PRECEDENCE[PolicyEffect.WARN]


class TestRoleRank:
    def test_owner_highest(self) -> None:
        assert _ROLE_RANK[OrgRole.OWNER] == max(_ROLE_RANK.values())

    def test_member_lowest(self) -> None:
        assert _ROLE_RANK[OrgRole.MEMBER] == min(_ROLE_RANK.values())

    def test_all_roles_covered(self) -> None:
        assert set(_ROLE_RANK.keys()) == set(OrgRole)


# ---------------------------------------------------------------------------
# Default allow
# ---------------------------------------------------------------------------


class TestDefaultAllow:
    def test_empty_snapshot_returns_allow(self) -> None:
        decision = evaluate(_snap([]), _ctx())
        assert decision.effect == PolicyEffect.ALLOW
        assert decision.policy_id is None
        assert decision.matched_rule is None

    def test_default_message(self) -> None:
        decision = evaluate(_snap([]), _ctx())
        assert decision.message == _DEFAULT_MESSAGE

    def test_snapshot_id_propagated(self) -> None:
        decision = evaluate(_snap([], snap_id="snap_xyz"), _ctx())
        assert decision.snapshot_id == "snap_xyz"

    def test_trigger_propagated(self) -> None:
        decision = evaluate(_snap([]), _ctx(trigger=PolicyTrigger.ON_QUERY))
        assert decision.trigger == PolicyTrigger.ON_QUERY

    def test_no_matching_trigger_returns_allow(self) -> None:
        rule = _rule(trigger=PolicyTrigger.ON_QUERY, effect=PolicyEffect.DENY)
        decision = evaluate(_snap([_policy([rule])]), _ctx(trigger=PolicyTrigger.ON_RELEASE))
        assert decision.effect == PolicyEffect.ALLOW


# ---------------------------------------------------------------------------
# Single effect evaluations
# ---------------------------------------------------------------------------


class TestAllow:
    def test_explicit_allow_rule(self) -> None:
        rule = _rule(effect=PolicyEffect.ALLOW, message="Allowed.")
        decision = evaluate(_snap([_policy([rule])]), _ctx())
        assert decision.effect == PolicyEffect.ALLOW
        assert decision.message == "Allowed."
        assert decision.policy_id == "pol_001"

    def test_matched_rule_present(self) -> None:
        rule = _rule(effect=PolicyEffect.ALLOW, message="ok")
        decision = evaluate(_snap([_policy([rule])]), _ctx())
        assert decision.matched_rule is not None
        assert decision.matched_rule.effect == PolicyEffect.ALLOW


class TestWarn:
    def test_warn_rule_fires(self) -> None:
        rule = _rule(effect=PolicyEffect.WARN, message="Advisory: check sources.")
        decision = evaluate(_snap([_policy([rule])]), _ctx())
        assert decision.effect == PolicyEffect.WARN
        assert decision.message == "Advisory: check sources."

    def test_warn_includes_matched_rule(self) -> None:
        rule = _rule(effect=PolicyEffect.WARN, message="w")
        decision = evaluate(_snap([_policy([rule])]), _ctx())
        assert decision.matched_rule is not None


class TestRedact:
    def test_redact_rule_fires_with_tag(self) -> None:
        rule = _rule(effect=PolicyEffect.REDACT, message="Redacted.", matched_tags=["confidential"])
        decision = evaluate(_snap([_policy([rule])]), _ctx(document_tags=["confidential"]))
        assert decision.effect == PolicyEffect.REDACT

    def test_redact_no_fire_without_tag(self) -> None:
        rule = _rule(effect=PolicyEffect.REDACT, matched_tags=["confidential"])
        decision = evaluate(_snap([_policy([rule])]), _ctx(document_tags=[]))
        assert decision.effect == PolicyEffect.ALLOW


class TestRequireApproval:
    def test_require_approval_fires(self) -> None:
        rule = _rule(effect=PolicyEffect.REQUIRE_APPROVAL, message="Senior review required.")
        decision = evaluate(_snap([_policy([rule])]), _ctx())
        assert decision.effect == PolicyEffect.REQUIRE_APPROVAL

    def test_require_approval_on_query_trigger(self) -> None:
        rule = _rule(trigger=PolicyTrigger.ON_QUERY, effect=PolicyEffect.REQUIRE_APPROVAL, message="Query held.")
        decision = evaluate(_snap([_policy([rule])]), _ctx(trigger=PolicyTrigger.ON_QUERY))
        assert decision.effect == PolicyEffect.REQUIRE_APPROVAL


class TestDeny:
    def test_deny_rule_fires(self) -> None:
        rule = _rule(
            trigger=PolicyTrigger.ON_QUERY,
            effect=PolicyEffect.DENY,
            message="Litigation hold: query blocked.",
            detected_topics=["litigation hold"],
        )
        decision = evaluate(
            _snap([_policy([rule])]),
            _ctx(trigger=PolicyTrigger.ON_QUERY, detected_topics=["litigation hold"]),
        )
        assert decision.effect == PolicyEffect.DENY
        assert decision.message == "Litigation hold: query blocked."

    def test_deny_no_fire_without_topic(self) -> None:
        rule = _rule(trigger=PolicyTrigger.ON_QUERY, effect=PolicyEffect.DENY, detected_topics=["litigation hold"])
        decision = evaluate(
            _snap([_policy([rule])]),
            _ctx(trigger=PolicyTrigger.ON_QUERY, detected_topics=[]),
        )
        assert decision.effect == PolicyEffect.ALLOW


class TestRequireLedger:
    def test_require_ledger_fires(self) -> None:
        rule = _rule(effect=PolicyEffect.REQUIRE_LEDGER, message="Must have durable ledger entry.")
        decision = evaluate(_snap([_policy([rule])]), _ctx())
        assert decision.effect == PolicyEffect.REQUIRE_LEDGER


# ---------------------------------------------------------------------------
# Multiple matching rules — most restrictive wins
# ---------------------------------------------------------------------------


class TestMultipleRules:
    def test_deny_beats_allow(self) -> None:
        rules = [_rule(effect=PolicyEffect.ALLOW), _rule(effect=PolicyEffect.DENY, message="d")]
        assert evaluate(_snap([_policy(rules)]), _ctx()).effect == PolicyEffect.DENY

    def test_deny_beats_warn(self) -> None:
        rules = [_rule(effect=PolicyEffect.WARN), _rule(effect=PolicyEffect.DENY, message="d")]
        assert evaluate(_snap([_policy(rules)]), _ctx()).effect == PolicyEffect.DENY

    def test_require_approval_beats_redact(self) -> None:
        rules = [_rule(effect=PolicyEffect.REDACT), _rule(effect=PolicyEffect.REQUIRE_APPROVAL, message="h")]
        assert evaluate(_snap([_policy(rules)]), _ctx()).effect == PolicyEffect.REQUIRE_APPROVAL

    def test_redact_beats_warn(self) -> None:
        rules = [_rule(effect=PolicyEffect.WARN), _rule(effect=PolicyEffect.REDACT, message="r")]
        assert evaluate(_snap([_policy(rules)]), _ctx()).effect == PolicyEffect.REDACT

    def test_warn_beats_allow(self) -> None:
        rules = [_rule(effect=PolicyEffect.ALLOW), _rule(effect=PolicyEffect.WARN, message="w")]
        assert evaluate(_snap([_policy(rules)]), _ctx()).effect == PolicyEffect.WARN

    def test_winning_policy_id_correct(self) -> None:
        pol_a = _policy([_rule(effect=PolicyEffect.WARN, message="w")], pid="pol_a")
        pol_b = _policy([_rule(effect=PolicyEffect.DENY, message="d")], pid="pol_b")
        decision = evaluate(_snap([pol_a, pol_b]), _ctx())
        assert decision.effect == PolicyEffect.DENY
        assert decision.policy_id == "pol_b"

    def test_three_policies_highest_wins(self) -> None:
        snap = _snap([
            _policy([_rule(effect=PolicyEffect.ALLOW)], pid="p1"),
            _policy([_rule(effect=PolicyEffect.REQUIRE_APPROVAL, message="h")], pid="p2"),
            _policy([_rule(effect=PolicyEffect.WARN)], pid="p3"),
        ])
        decision = evaluate(snap, _ctx())
        assert decision.effect == PolicyEffect.REQUIRE_APPROVAL
        assert decision.policy_id == "p2"

    def test_full_priority_chain(self) -> None:
        effects = list(PolicyEffect)
        rules = [_rule(effect=e, message=e.value) for e in effects]
        decision = evaluate(_snap([_policy(rules)]), _ctx())
        assert decision.effect == PolicyEffect.DENY


# ---------------------------------------------------------------------------
# Trigger filtering
# ---------------------------------------------------------------------------


class TestTriggerFiltering:
    def test_wrong_trigger_not_evaluated(self) -> None:
        rule = _rule(trigger=PolicyTrigger.ON_QUERY, effect=PolicyEffect.DENY)
        decision = evaluate(_snap([_policy([rule])]), _ctx(trigger=PolicyTrigger.ON_RETRIEVAL))
        assert decision.effect == PolicyEffect.ALLOW

    def test_correct_trigger_evaluated(self) -> None:
        rule = _rule(trigger=PolicyTrigger.ON_GENERATION, effect=PolicyEffect.WARN)
        decision = evaluate(_snap([_policy([rule])]), _ctx(trigger=PolicyTrigger.ON_GENERATION))
        assert decision.effect == PolicyEffect.WARN

    def test_mixed_triggers_only_matching_counted(self) -> None:
        rules = [
            _rule(trigger=PolicyTrigger.ON_QUERY, effect=PolicyEffect.DENY, message="d"),
            _rule(trigger=PolicyTrigger.ON_RELEASE, effect=PolicyEffect.WARN, message="w"),
        ]
        decision = evaluate(_snap([_policy(rules)]), _ctx(trigger=PolicyTrigger.ON_RELEASE))
        assert decision.effect == PolicyEffect.WARN


# ---------------------------------------------------------------------------
# Condition matching
# ---------------------------------------------------------------------------


class TestConditionMatching:
    def test_tag_subset_required_partial_no_match(self) -> None:
        rule = _rule(effect=PolicyEffect.DENY, matched_tags=["confidential", "pii"])
        decision = evaluate(_snap([_policy([rule])]), _ctx(document_tags=["confidential"]))
        assert decision.effect == PolicyEffect.ALLOW

    def test_tag_full_subset_fires(self) -> None:
        rule = _rule(effect=PolicyEffect.DENY, matched_tags=["confidential"])
        decision = evaluate(_snap([_policy([rule])]), _ctx(document_tags=["confidential", "other"]))
        assert decision.effect == PolicyEffect.DENY

    def test_topic_not_present_no_match(self) -> None:
        rule = _rule(effect=PolicyEffect.DENY, detected_topics=["litigation hold"])
        decision = evaluate(_snap([_policy([rule])]), _ctx(detected_topics=["other topic"]))
        assert decision.effect == PolicyEffect.ALLOW

    def test_pii_required_but_absent(self) -> None:
        rule = _rule(effect=PolicyEffect.REDACT, requires_pii=True)
        decision = evaluate(_snap([_policy([rule])]), _ctx(pii_detected=False))
        assert decision.effect == PolicyEffect.ALLOW

    def test_pii_required_and_present(self) -> None:
        rule = _rule(effect=PolicyEffect.REDACT, requires_pii=True, message="PII redacted.")
        decision = evaluate(_snap([_policy([rule])]), _ctx(pii_detected=True))
        assert decision.effect == PolicyEffect.REDACT

    def test_role_insufficient(self) -> None:
        rule = _rule(effect=PolicyEffect.WARN, required_role=OrgRole.REVIEWER)
        decision = evaluate(_snap([_policy([rule])]), _ctx(role=OrgRole.MEMBER))
        assert decision.effect == PolicyEffect.ALLOW

    def test_role_exact_minimum_fires(self) -> None:
        rule = _rule(effect=PolicyEffect.WARN, required_role=OrgRole.REVIEWER)
        decision = evaluate(_snap([_policy([rule])]), _ctx(role=OrgRole.REVIEWER))
        assert decision.effect == PolicyEffect.WARN

    def test_role_above_minimum_fires(self) -> None:
        rule = _rule(effect=PolicyEffect.WARN, required_role=OrgRole.MEMBER)
        decision = evaluate(_snap([_policy([rule])]), _ctx(role=OrgRole.OWNER))
        assert decision.effect == PolicyEffect.WARN

    def test_empty_condition_matches_everything(self) -> None:
        rule = _rule(effect=PolicyEffect.WARN)
        decision = evaluate(_snap([_policy([rule])]), _ctx())
        assert decision.effect == PolicyEffect.WARN


# ---------------------------------------------------------------------------
# Scope filtering
# ---------------------------------------------------------------------------


class TestScopeFiltering:
    def test_org_wide_always_matches(self) -> None:
        rule = _rule(effect=PolicyEffect.WARN)
        pol = _policy([rule], scope=PolicyScope.ORG_WIDE)
        assert evaluate(_snap([pol]), _ctx(role=OrgRole.MEMBER)).effect == PolicyEffect.WARN

    def test_role_specific_matches_exact_role(self) -> None:
        rule = _rule(effect=PolicyEffect.DENY, message="denied")
        pol = _policy([rule], scope=PolicyScope.ROLE_SPECIFIC, scope_target="reviewer")
        assert evaluate(_snap([pol]), _ctx(role=OrgRole.REVIEWER)).effect == PolicyEffect.DENY

    def test_role_specific_no_match_different_role(self) -> None:
        rule = _rule(effect=PolicyEffect.DENY)
        pol = _policy([rule], scope=PolicyScope.ROLE_SPECIFIC, scope_target="reviewer")
        assert evaluate(_snap([pol]), _ctx(role=OrgRole.OWNER)).effect == PolicyEffect.ALLOW

    def test_document_tag_scope_matches_when_tag_present(self) -> None:
        rule = _rule(effect=PolicyEffect.WARN)
        pol = _policy([rule], scope=PolicyScope.DOCUMENT_TAG_SPECIFIC, scope_target="classified")
        assert evaluate(_snap([pol]), _ctx(document_tags=["classified"])).effect == PolicyEffect.WARN

    def test_document_tag_scope_no_match_without_tag(self) -> None:
        rule = _rule(effect=PolicyEffect.WARN)
        pol = _policy([rule], scope=PolicyScope.DOCUMENT_TAG_SPECIFIC, scope_target="classified")
        assert evaluate(_snap([pol]), _ctx(document_tags=["public"])).effect == PolicyEffect.ALLOW

    def test_inactive_policy_ignored(self) -> None:
        rule = _rule(effect=PolicyEffect.DENY, message="denied")
        pol = _policy([rule], is_active=False)
        assert evaluate(_snap([pol]), _ctx()).effect == PolicyEffect.ALLOW


# ---------------------------------------------------------------------------
# Snapshot generation
# ---------------------------------------------------------------------------


class TestCreateSnapshot:
    def test_returns_snapshot(self) -> None:
        snap = create_snapshot(_ORG, _UID, [_policy([_rule()])])
        assert isinstance(snap, PolicySnapshot)

    def test_org_id_set(self) -> None:
        assert create_snapshot(_ORG, _UID, []).org_id == _ORG

    def test_created_by_set(self) -> None:
        assert create_snapshot(_ORG, _UID, []).created_by == _UID

    def test_fresh_uuid_each_call(self) -> None:
        s1 = create_snapshot(_ORG, _UID, [])
        s2 = create_snapshot(_ORG, _UID, [])
        assert s1.id != s2.id

    def test_only_active_policies_included(self) -> None:
        active = _policy([_rule()], pid="pol_a", is_active=True)
        inactive = _policy([_rule()], pid="pol_b", is_active=False)
        snap = create_snapshot(_ORG, _UID, [active, inactive])
        assert len(snap.policies) == 1
        assert snap.policies[0].id == "pol_a"

    def test_empty_input_allowed(self) -> None:
        assert create_snapshot(_ORG, _UID, []).policies == []

    def test_created_at_utc(self) -> None:
        snap = create_snapshot(_ORG, _UID, [])
        offset = snap.created_at.utcoffset()
        assert offset is not None and offset.total_seconds() == 0

    def test_snapshot_frozen(self) -> None:
        snap = create_snapshot(_ORG, _UID, [])
        with pytest.raises(Exception):
            snap.org_id = "other"  # type: ignore[misc]

    def test_evaluate_against_returns_allow_when_empty(self) -> None:
        snap = create_snapshot(_ORG, _UID, [])
        assert evaluate(snap, _ctx()).effect == PolicyEffect.ALLOW


# ---------------------------------------------------------------------------
# Default snapshot (personal org)
# ---------------------------------------------------------------------------


class TestDefaultSnapshot:
    def test_stable_id(self) -> None:
        assert default_snapshot(_ORG).id == _DEFAULT_SNAPSHOT_ID

    def test_org_id_set(self) -> None:
        assert default_snapshot(_ORG).org_id == _ORG

    def test_empty_policies(self) -> None:
        assert default_snapshot(_ORG).policies == []

    def test_all_triggers_return_allow(self) -> None:
        snap = default_snapshot(_ORG)
        for trigger in PolicyTrigger:
            assert evaluate(snap, _ctx(trigger=trigger)).effect == PolicyEffect.ALLOW

    def test_deterministic_id(self) -> None:
        assert default_snapshot(_ORG).id == default_snapshot(_ORG).id


# ---------------------------------------------------------------------------
# Edge cases
# ---------------------------------------------------------------------------


class TestEdgeCases:
    def test_all_triggers_evaluated_independently(self) -> None:
        rules = [_rule(trigger=t, effect=PolicyEffect.WARN, message="w") for t in PolicyTrigger]
        snap = _snap([_policy(rules)])
        for trigger in PolicyTrigger:
            assert evaluate(snap, _ctx(trigger=trigger)).effect == PolicyEffect.WARN

    def test_policy_with_no_rules_contributes_nothing(self) -> None:
        assert evaluate(_snap([_policy([])]), _ctx()).effect == PolicyEffect.ALLOW

    def test_org_wide_and_role_specific_deny_wins(self) -> None:
        org_wide = _policy([_rule(effect=PolicyEffect.WARN)], pid="p1")
        role_deny = _policy(
            [_rule(effect=PolicyEffect.DENY, message="d")],
            pid="p2",
            scope=PolicyScope.ROLE_SPECIFIC,
            scope_target="reviewer",
        )
        snap = _snap([org_wide, role_deny])
        decision = evaluate(snap, _ctx(role=OrgRole.REVIEWER))
        assert decision.effect == PolicyEffect.DENY
        assert decision.policy_id == "p2"

    def test_member_only_sees_org_wide(self) -> None:
        org_wide = _policy([_rule(effect=PolicyEffect.WARN)], pid="p1")
        role_deny = _policy(
            [_rule(effect=PolicyEffect.DENY)], pid="p2",
            scope=PolicyScope.ROLE_SPECIFIC, scope_target="reviewer",
        )
        snap = _snap([org_wide, role_deny])
        decision = evaluate(snap, _ctx(role=OrgRole.MEMBER))
        assert decision.effect == PolicyEffect.WARN
        assert decision.policy_id == "p1"

    def test_combined_condition_all_must_match(self) -> None:
        rule = PolicyRule(
            trigger=PolicyTrigger.ON_QUERY,
            condition=PolicyCondition(
                matched_tags=["confidential"],
                detected_topics=["litigation hold"],
                requires_pii=True,
            ),
            effect=PolicyEffect.DENY,
            message="All conditions required.",
        )
        snap = _snap([_policy([rule])])
        full_ctx = _ctx(
            trigger=PolicyTrigger.ON_QUERY,
            document_tags=["confidential"],
            detected_topics=["litigation hold"],
            pii_detected=True,
        )
        assert evaluate(snap, full_ctx).effect == PolicyEffect.DENY
        # Remove pii — should not fire
        no_pii = _ctx(
            trigger=PolicyTrigger.ON_QUERY,
            document_tags=["confidential"],
            detected_topics=["litigation hold"],
            pii_detected=False,
        )
        assert evaluate(snap, no_pii).effect == PolicyEffect.ALLOW
