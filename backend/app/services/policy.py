"""Policy Engine evaluation service — pure, deterministic, no I/O.

Evaluates a PolicySnapshot against a runtime context and returns a PolicyDecision.
All effects are deterministic: no LLM calls, no external signals.
Firestore persistence of snapshots is the responsibility of the organization
service (implemented in a later task).
"""
from __future__ import annotations

import uuid
from datetime import datetime, timezone

from app.models.policy import (
    OrgRole,
    Policy,
    PolicyCondition,
    PolicyDecision,
    PolicyEffect,
    PolicyEvaluationContext,
    PolicyRule,
    PolicyScope,
    PolicySnapshot,
)

# ---------------------------------------------------------------------------
# Constants
# ---------------------------------------------------------------------------

_DEFAULT_SNAPSHOT_ID = "default"
_DEFAULT_MESSAGE = "No policy rule matched; default allow."

# ---------------------------------------------------------------------------
# Effect precedence — higher wins when multiple rules match.
# ---------------------------------------------------------------------------

_EFFECT_PRECEDENCE: dict[PolicyEffect, int] = {
    PolicyEffect.ALLOW:            0,
    PolicyEffect.REQUIRE_LEDGER:   1,
    PolicyEffect.WARN:             2,
    PolicyEffect.REDACT:           3,
    PolicyEffect.REQUIRE_APPROVAL: 4,
    PolicyEffect.DENY:             5,
}

# ---------------------------------------------------------------------------
# Role rank — higher number = more privileged.
# ---------------------------------------------------------------------------

_ROLE_RANK: dict[OrgRole, int] = {
    OrgRole.MEMBER:      0,
    OrgRole.CONTRIBUTOR: 1,
    OrgRole.REVIEWER:    2,
    OrgRole.AUDITOR:     3,
    OrgRole.ADMIN:       4,
    OrgRole.OWNER:       5,
}


# ---------------------------------------------------------------------------
# Internal helpers
# ---------------------------------------------------------------------------


def _condition_matches(condition: PolicyCondition, ctx: PolicyEvaluationContext) -> bool:
    """All constraints in the condition must hold simultaneously."""
    if condition.matched_tags:
        if not set(condition.matched_tags).issubset(set(ctx.document_tags)):
            return False
    if condition.detected_topics:
        if not set(condition.detected_topics).issubset(set(ctx.detected_topics)):
            return False
    if condition.required_role is not None:
        if _ROLE_RANK[ctx.actor_role] < _ROLE_RANK[condition.required_role]:
            return False
    if condition.requires_pii and not ctx.pii_detected:
        return False
    return True


def _scope_matches(policy: Policy, ctx: PolicyEvaluationContext) -> bool:
    """Check whether the policy's scope includes this request context."""
    if policy.scope == PolicyScope.ORG_WIDE:
        return True
    if policy.scope == PolicyScope.ROLE_SPECIFIC:
        return (
            policy.scope_target is not None
            and ctx.actor_role.value == policy.scope_target
        )
    if policy.scope == PolicyScope.DOCUMENT_TAG_SPECIFIC:
        return (
            policy.scope_target is not None
            and policy.scope_target in ctx.document_tags
        )
    return True


def _matching_rules(
    snapshot: PolicySnapshot,
    ctx: PolicyEvaluationContext,
) -> list[tuple[PolicyRule, str]]:
    """Return (rule, policy_id) pairs whose trigger and condition match the context."""
    matches: list[tuple[PolicyRule, str]] = []
    for policy in snapshot.policies:
        if not policy.is_active:
            continue
        if not _scope_matches(policy, ctx):
            continue
        for rule in policy.rules:
            if rule.trigger != ctx.trigger:
                continue
            if _condition_matches(rule.condition, ctx):
                matches.append((rule, policy.id))
    return matches


# ---------------------------------------------------------------------------
# Public API
# ---------------------------------------------------------------------------


def evaluate(snapshot: PolicySnapshot, ctx: PolicyEvaluationContext) -> PolicyDecision:
    """Evaluate the snapshot against the context and return the winning decision.

    When multiple rules match, the most restrictive effect wins (highest
    _EFFECT_PRECEDENCE). Ties broken by first-match order within iteration.
    Returns default-allow when no rules match or the snapshot is empty.
    """
    matches = _matching_rules(snapshot, ctx)

    if not matches:
        return PolicyDecision(
            trigger=ctx.trigger,
            effect=PolicyEffect.ALLOW,
            policy_id=None,
            snapshot_id=snapshot.id,
            message=_DEFAULT_MESSAGE,
        )

    best_rule, best_pid = matches[0]
    best_prec = _EFFECT_PRECEDENCE[best_rule.effect]

    for rule, pid in matches[1:]:
        prec = _EFFECT_PRECEDENCE[rule.effect]
        if prec > best_prec:
            best_prec = prec
            best_rule = rule
            best_pid = pid

    return PolicyDecision(
        trigger=ctx.trigger,
        effect=best_rule.effect,
        policy_id=best_pid,
        snapshot_id=snapshot.id,
        message=best_rule.message,
        matched_rule=best_rule,
    )


def create_snapshot(
    org_id: str,
    created_by: str,
    active_policies: list[Policy],
) -> PolicySnapshot:
    """Bundle the currently active policies into an immutable snapshot.

    Only is_active=True policies are included. Persistence to Firestore is
    delegated to the organization service (later task).
    """
    return PolicySnapshot(
        id=str(uuid.uuid4()),
        org_id=org_id,
        policies=[p for p in active_policies if p.is_active],
        created_at=datetime.now(tz=timezone.utc),
        created_by=created_by,
    )


def default_snapshot(org_id: str) -> PolicySnapshot:
    """Return the deterministic default-allow snapshot for a personal org.

    Empty policies list → evaluate() always returns default-allow.
    Stable id "default" so ledger entries written before a real policy is
    authored always reference a known value.
    """
    return PolicySnapshot(
        id=_DEFAULT_SNAPSHOT_ID,
        org_id=org_id,
        policies=[],
        created_at=datetime.now(tz=timezone.utc),
        created_by=org_id,
    )
