"""Tests: Policy Engine integration in the chat pipeline.

All external services (embed, retrieve, LLM, Firestore, policy evaluation) are mocked.
Tests verify SSE event shape, assistant-message persistence, and ledger payload
for each policy effect (allow, warn, redact, require_approval, deny, require_ledger).
"""
from __future__ import annotations

import contextlib
import json
from collections.abc import AsyncGenerator, Generator
from datetime import datetime, timezone
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from app.models.chunk import ChunkCitation
from app.models.conversation import Conversation, Message
from app.models.ledger import PolicyRecord
from app.models.policy import (
    PolicyDecision,
    PolicyEffect,
    PolicyEvaluationContext,
    PolicySnapshot,
    PolicyTrigger,
)

_T0 = datetime(2026, 6, 25, 6, 0, 0, tzinfo=timezone.utc)
_UID = "uid_policy_test"
_CONV_ID = "conv_policy_001"
_MSG_ID = "msg_asst_policy_001"
_SNAP_ID = "snap_default"


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------


def _make_conv() -> Conversation:
    return Conversation(
        id=_CONV_ID,
        owner_uid=_UID,
        title="Policy test conv",
        title_generated=True,
        document_ids=["doc_001"],
        created_at=_T0,
        updated_at=_T0,
    )


def _make_message() -> Message:
    return Message(
        id="msg_user_001",
        conversation_id=_CONV_ID,
        uid=_UID,
        role="user",
        content="Hello",
        created_at=_T0,
    )


def _make_snapshot() -> PolicySnapshot:
    return PolicySnapshot(
        id=_SNAP_ID,
        org_id=_UID,
        policies=[],
        created_at=_T0,
        created_by=_UID,
    )


def _make_decision(
    trigger: PolicyTrigger,
    effect: PolicyEffect,
    message: str = "Policy decision.",
    policy_id: str | None = None,
) -> PolicyDecision:
    return PolicyDecision(
        trigger=trigger,
        effect=effect,
        policy_id=policy_id,
        snapshot_id=_SNAP_ID,
        message=message,
    )


# ---------------------------------------------------------------------------
# SSE parsing helpers
# ---------------------------------------------------------------------------


def _event_types(chunks: list[str]) -> list[str]:
    types: list[str] = []
    for chunk in chunks:
        for line in chunk.strip().split("\n"):
            if line.startswith("event: "):
                types.append(line[7:])
    return types


def _policy_events(chunks: list[str]) -> list[dict[str, object]]:
    events: list[dict[str, object]] = []
    for chunk in chunks:
        lines = chunk.strip().split("\n")
        for i, line in enumerate(lines):
            if line == "event: policy" and i + 1 < len(lines):
                data_line = lines[i + 1]
                if data_line.startswith("data: "):
                    events.append(json.loads(data_line[6:]))
    return events


# ---------------------------------------------------------------------------
# Patch context manager
# ---------------------------------------------------------------------------


class _ChatPolicyMocks:
    list_messages: MagicMock
    embed_query: AsyncMock
    create_message: MagicMock
    retrieve: AsyncMock
    build_context: MagicMock
    create_assistant_message: MagicMock
    stream_response: AsyncMock
    log_decision: AsyncMock
    default_snapshot: MagicMock
    policy_evaluate: MagicMock


@contextlib.contextmanager
def _patch_policy_chat(
    query_effect: PolicyEffect = PolicyEffect.ALLOW,
    release_effect: PolicyEffect = PolicyEffect.ALLOW,
    query_message: str = "Default allow.",
    release_message: str = "Default allow.",
    tokens: list[str] | None = None,
    citations: list[ChunkCitation] | None = None,
) -> Generator[_ChatPolicyMocks, None, None]:
    mocks = _ChatPolicyMocks()
    snap = _make_snapshot()

    async def _fake_stream(
        history: object, context: object, content: object
    ) -> AsyncGenerator[str, None]:
        for t in tokens or ["Hello", " world"]:
            yield t

    asst_msg = MagicMock()
    asst_msg.id = _MSG_ID

    def _fake_evaluate(snapshot: object, ctx: object) -> PolicyDecision:
        assert isinstance(ctx, PolicyEvaluationContext)
        if ctx.trigger == PolicyTrigger.ON_QUERY:
            return _make_decision(ctx.trigger, query_effect, query_message)
        return _make_decision(ctx.trigger, release_effect, release_message)

    with (
        patch("app.api.chat.list_messages", return_value=[_make_message()]) as p1,
        patch("app.api.chat.embed_query", new_callable=AsyncMock, return_value=[0.1] * 768) as p2,
        patch("app.api.chat.create_message") as p3,
        patch("app.api.chat.retrieve", new_callable=AsyncMock, return_value=citations or []) as p4,
        patch("app.api.chat.build_context", return_value="ctx") as p5,
        patch("app.api.chat.create_assistant_message", return_value=asst_msg) as p6,
        patch("app.api.chat.stream_response", side_effect=_fake_stream) as p7,
        patch("app.api.chat.log_decision", new_callable=AsyncMock) as p8,
        patch("app.api.chat.default_snapshot", return_value=snap) as p9,
        patch("app.api.chat.policy_evaluate", side_effect=_fake_evaluate) as p10,
    ):
        mocks.list_messages = p1
        mocks.embed_query = p2
        mocks.create_message = p3
        mocks.retrieve = p4
        mocks.build_context = p5
        mocks.create_assistant_message = p6
        mocks.stream_response = p7
        mocks.log_decision = p8
        mocks.default_snapshot = p9
        mocks.policy_evaluate = p10
        yield mocks


# ===========================================================================
# Allow path
# ===========================================================================


class TestAllowPath:
    async def test_allow_emits_done(self) -> None:
        from app.api.chat import _stream
        chunks: list[str] = []
        with _patch_policy_chat() as _:
            async for chunk in _stream(_make_conv(), "q", None, _UID):
                chunks.append(chunk)
        assert "done" in _event_types(chunks)

    async def test_allow_no_policy_sse(self) -> None:
        from app.api.chat import _stream
        chunks: list[str] = []
        with _patch_policy_chat() as _:
            async for chunk in _stream(_make_conv(), "q", None, _UID):
                chunks.append(chunk)
        assert "policy" not in _event_types(chunks)

    async def test_allow_saves_assistant_message(self) -> None:
        from app.api.chat import _stream
        with _patch_policy_chat() as m:
            async for _ in _stream(_make_conv(), "q", None, _UID):
                pass
        m.create_assistant_message.assert_called_once()

    async def test_allow_calls_log_decision(self) -> None:
        from app.api.chat import _stream
        with _patch_policy_chat() as m:
            async for _ in _stream(_make_conv(), "q", None, _UID):
                pass
        m.log_decision.assert_called_once()


# ===========================================================================
# Warn path
# ===========================================================================


class TestWarnPath:
    async def test_warn_emits_policy_sse(self) -> None:
        from app.api.chat import _stream
        chunks: list[str] = []
        with _patch_policy_chat(release_effect=PolicyEffect.WARN, release_message="Advisory") as _:
            async for chunk in _stream(_make_conv(), "q", None, _UID):
                chunks.append(chunk)
        assert "policy" in _event_types(chunks)

    async def test_warn_emits_done(self) -> None:
        from app.api.chat import _stream
        chunks: list[str] = []
        with _patch_policy_chat(release_effect=PolicyEffect.WARN) as _:
            async for chunk in _stream(_make_conv(), "q", None, _UID):
                chunks.append(chunk)
        assert "done" in _event_types(chunks)

    async def test_warn_saves_assistant_message(self) -> None:
        from app.api.chat import _stream
        with _patch_policy_chat(release_effect=PolicyEffect.WARN) as m:
            async for _ in _stream(_make_conv(), "q", None, _UID):
                pass
        m.create_assistant_message.assert_called_once()

    async def test_warn_policy_sse_has_correct_effect(self) -> None:
        from app.api.chat import _stream
        chunks: list[str] = []
        with _patch_policy_chat(release_effect=PolicyEffect.WARN, release_message="Watch out") as _:
            async for chunk in _stream(_make_conv(), "q", None, _UID):
                chunks.append(chunk)
        events = _policy_events(chunks)
        assert len(events) == 1
        assert events[0]["effect"] == "warn"
        assert events[0]["message"] == "Watch out"

    async def test_warn_no_error_sse(self) -> None:
        from app.api.chat import _stream
        chunks: list[str] = []
        with _patch_policy_chat(release_effect=PolicyEffect.WARN) as _:
            async for chunk in _stream(_make_conv(), "q", None, _UID):
                chunks.append(chunk)
        assert "error" not in _event_types(chunks)


# ===========================================================================
# Redact path
# ===========================================================================


class TestRedactPath:
    async def test_redact_emits_policy_sse(self) -> None:
        from app.api.chat import _stream
        chunks: list[str] = []
        with _patch_policy_chat(
            release_effect=PolicyEffect.REDACT, release_message="Confidential"
        ) as _:
            async for chunk in _stream(_make_conv(), "q", None, _UID):
                chunks.append(chunk)
        assert "policy" in _event_types(chunks)

    async def test_redact_replaces_accumulated_content(self) -> None:
        from app.api.chat import _stream
        with _patch_policy_chat(
            release_effect=PolicyEffect.REDACT,
            release_message="Classified",
            tokens=["Secret content"],
        ) as m:
            async for _ in _stream(_make_conv(), "q", None, _UID):
                pass
        saved_content = m.create_assistant_message.call_args[0][2]
        assert "Redacted" in saved_content
        assert "Secret content" not in saved_content

    async def test_redact_still_emits_done(self) -> None:
        from app.api.chat import _stream
        chunks: list[str] = []
        with _patch_policy_chat(release_effect=PolicyEffect.REDACT) as _:
            async for chunk in _stream(_make_conv(), "q", None, _UID):
                chunks.append(chunk)
        assert "done" in _event_types(chunks)

    async def test_redact_policy_sse_has_correct_effect(self) -> None:
        from app.api.chat import _stream
        chunks: list[str] = []
        with _patch_policy_chat(
            release_effect=PolicyEffect.REDACT, release_message="Redact msg"
        ) as _:
            async for chunk in _stream(_make_conv(), "q", None, _UID):
                chunks.append(chunk)
        events = _policy_events(chunks)
        assert events[0]["effect"] == "redact"

    async def test_redact_no_error_sse(self) -> None:
        from app.api.chat import _stream
        chunks: list[str] = []
        with _patch_policy_chat(release_effect=PolicyEffect.REDACT) as _:
            async for chunk in _stream(_make_conv(), "q", None, _UID):
                chunks.append(chunk)
        assert "error" not in _event_types(chunks)


# ===========================================================================
# Require approval path
# ===========================================================================


class TestRequireApprovalPath:
    async def test_require_approval_emits_policy_sse(self) -> None:
        from app.api.chat import _stream
        chunks: list[str] = []
        with _patch_policy_chat(
            release_effect=PolicyEffect.REQUIRE_APPROVAL, release_message="Senior review required"
        ) as _:
            async for chunk in _stream(_make_conv(), "q", None, _UID):
                chunks.append(chunk)
        assert "policy" in _event_types(chunks)

    async def test_require_approval_no_done_event(self) -> None:
        from app.api.chat import _stream
        chunks: list[str] = []
        with _patch_policy_chat(release_effect=PolicyEffect.REQUIRE_APPROVAL) as _:
            async for chunk in _stream(_make_conv(), "q", None, _UID):
                chunks.append(chunk)
        assert "done" not in _event_types(chunks)

    async def test_require_approval_no_error_event(self) -> None:
        from app.api.chat import _stream
        chunks: list[str] = []
        with _patch_policy_chat(release_effect=PolicyEffect.REQUIRE_APPROVAL) as _:
            async for chunk in _stream(_make_conv(), "q", None, _UID):
                chunks.append(chunk)
        assert "error" not in _event_types(chunks)

    async def test_require_approval_no_assistant_message_saved(self) -> None:
        from app.api.chat import _stream
        with _patch_policy_chat(release_effect=PolicyEffect.REQUIRE_APPROVAL) as m:
            async for _ in _stream(_make_conv(), "q", None, _UID):
                pass
        m.create_assistant_message.assert_not_called()

    async def test_require_approval_no_log_decision(self) -> None:
        from app.api.chat import _stream
        with _patch_policy_chat(release_effect=PolicyEffect.REQUIRE_APPROVAL) as m:
            async for _ in _stream(_make_conv(), "q", None, _UID):
                pass
        m.log_decision.assert_not_called()

    async def test_require_approval_policy_sse_correct_effect(self) -> None:
        from app.api.chat import _stream
        chunks: list[str] = []
        with _patch_policy_chat(
            release_effect=PolicyEffect.REQUIRE_APPROVAL, release_message="Held"
        ) as _:
            async for chunk in _stream(_make_conv(), "q", None, _UID):
                chunks.append(chunk)
        events = _policy_events(chunks)
        assert events[0]["effect"] == "require_approval"
        assert events[0]["message"] == "Held"


# ===========================================================================
# Deny path
# ===========================================================================


class TestDenyPath:
    async def test_deny_on_query_emits_error(self) -> None:
        from app.api.chat import _stream
        chunks: list[str] = []
        with _patch_policy_chat(
            query_effect=PolicyEffect.DENY, query_message="Query denied"
        ) as _:
            async for chunk in _stream(_make_conv(), "q", None, _UID):
                chunks.append(chunk)
        assert "error" in _event_types(chunks)

    async def test_deny_on_query_emits_policy_sse(self) -> None:
        from app.api.chat import _stream
        chunks: list[str] = []
        with _patch_policy_chat(query_effect=PolicyEffect.DENY, query_message="Blocked") as _:
            async for chunk in _stream(_make_conv(), "q", None, _UID):
                chunks.append(chunk)
        assert "policy" in _event_types(chunks)

    async def test_deny_on_query_no_done(self) -> None:
        from app.api.chat import _stream
        chunks: list[str] = []
        with _patch_policy_chat(query_effect=PolicyEffect.DENY) as _:
            async for chunk in _stream(_make_conv(), "q", None, _UID):
                chunks.append(chunk)
        assert "done" not in _event_types(chunks)

    async def test_deny_on_query_no_user_message_written(self) -> None:
        from app.api.chat import _stream
        with _patch_policy_chat(query_effect=PolicyEffect.DENY) as m:
            async for _ in _stream(_make_conv(), "q", None, _UID):
                pass
        m.create_message.assert_not_called()

    async def test_deny_on_query_no_embed(self) -> None:
        from app.api.chat import _stream
        with _patch_policy_chat(query_effect=PolicyEffect.DENY) as m:
            async for _ in _stream(_make_conv(), "q", None, _UID):
                pass
        m.embed_query.assert_not_called()

    async def test_deny_on_query_policy_sse_correct_trigger(self) -> None:
        from app.api.chat import _stream
        chunks: list[str] = []
        with _patch_policy_chat(query_effect=PolicyEffect.DENY, query_message="Blocked") as _:
            async for chunk in _stream(_make_conv(), "q", None, _UID):
                chunks.append(chunk)
        events = _policy_events(chunks)
        assert events[0]["effect"] == "deny"
        assert events[0]["trigger"] == "on-query"

    async def test_deny_on_release_emits_error(self) -> None:
        from app.api.chat import _stream
        chunks: list[str] = []
        with _patch_policy_chat(
            release_effect=PolicyEffect.DENY, release_message="Release denied"
        ) as _:
            async for chunk in _stream(_make_conv(), "q", None, _UID):
                chunks.append(chunk)
        assert "error" in _event_types(chunks)

    async def test_deny_on_release_no_done(self) -> None:
        from app.api.chat import _stream
        chunks: list[str] = []
        with _patch_policy_chat(release_effect=PolicyEffect.DENY) as _:
            async for chunk in _stream(_make_conv(), "q", None, _UID):
                chunks.append(chunk)
        assert "done" not in _event_types(chunks)

    async def test_deny_on_release_no_assistant_message_saved(self) -> None:
        from app.api.chat import _stream
        with _patch_policy_chat(release_effect=PolicyEffect.DENY) as m:
            async for _ in _stream(_make_conv(), "q", None, _UID):
                pass
        m.create_assistant_message.assert_not_called()

    async def test_deny_on_release_policy_sse_correct_trigger(self) -> None:
        from app.api.chat import _stream
        chunks: list[str] = []
        with _patch_policy_chat(
            release_effect=PolicyEffect.DENY, release_message="Denied"
        ) as _:
            async for chunk in _stream(_make_conv(), "q", None, _UID):
                chunks.append(chunk)
        events = _policy_events(chunks)
        assert events[0]["trigger"] == "on-release"


# ===========================================================================
# Default allow (personal org — empty snapshot)
# ===========================================================================


class TestDefaultAllow:
    async def test_default_snapshot_called_with_uid(self) -> None:
        from app.api.chat import _stream
        with _patch_policy_chat() as m:
            async for _ in _stream(_make_conv(), "q", None, _UID):
                pass
        m.default_snapshot.assert_called_once_with(_UID)

    async def test_policy_evaluate_called_at_both_seams(self) -> None:
        from app.api.chat import _stream
        with _patch_policy_chat() as m:
            async for _ in _stream(_make_conv(), "q", None, _UID):
                pass
        assert m.policy_evaluate.call_count == 2

    async def test_default_allow_emits_done(self) -> None:
        from app.api.chat import _stream
        chunks: list[str] = []
        with _patch_policy_chat() as _:
            async for chunk in _stream(_make_conv(), "q", None, _UID):
                chunks.append(chunk)
        assert "done" in _event_types(chunks)

    async def test_default_allow_no_policy_sse(self) -> None:
        from app.api.chat import _stream
        chunks: list[str] = []
        with _patch_policy_chat() as _:
            async for chunk in _stream(_make_conv(), "q", None, _UID):
                chunks.append(chunk)
        assert "policy" not in _event_types(chunks)

    async def test_default_allow_no_error_sse(self) -> None:
        from app.api.chat import _stream
        chunks: list[str] = []
        with _patch_policy_chat() as _:
            async for chunk in _stream(_make_conv(), "q", None, _UID):
                chunks.append(chunk)
        assert "error" not in _event_types(chunks)


# ===========================================================================
# Snapshot attached to ledger
# ===========================================================================


class TestSnapshotAttachedToLedger:
    async def test_policy_record_passed_to_log_decision(self) -> None:
        from app.api.chat import _stream
        with _patch_policy_chat() as m:
            async for _ in _stream(_make_conv(), "q", None, _UID):
                pass
        kwargs = m.log_decision.call_args[1]
        assert "policy_record" in kwargs
        assert isinstance(kwargs["policy_record"], PolicyRecord)

    async def test_policy_record_snapshot_id_matches(self) -> None:
        from app.api.chat import _stream
        with _patch_policy_chat() as m:
            async for _ in _stream(_make_conv(), "q", None, _UID):
                pass
        kwargs = m.log_decision.call_args[1]
        assert kwargs["policy_record"].snapshot_id == _SNAP_ID

    async def test_policy_record_contains_on_query_evaluation(self) -> None:
        from app.api.chat import _stream
        with _patch_policy_chat() as m:
            async for _ in _stream(_make_conv(), "q", None, _UID):
                pass
        evals = m.log_decision.call_args[1]["policy_record"].evaluations
        triggers = {e.trigger for e in evals}
        assert PolicyTrigger.ON_QUERY in triggers

    async def test_policy_record_contains_on_release_evaluation(self) -> None:
        from app.api.chat import _stream
        with _patch_policy_chat() as m:
            async for _ in _stream(_make_conv(), "q", None, _UID):
                pass
        evals = m.log_decision.call_args[1]["policy_record"].evaluations
        triggers = {e.trigger for e in evals}
        assert PolicyTrigger.ON_RELEASE in triggers

    async def test_policy_record_effect_matches_decision(self) -> None:
        from app.api.chat import _stream
        with _patch_policy_chat(release_effect=PolicyEffect.WARN) as m:
            async for _ in _stream(_make_conv(), "q", None, _UID):
                pass
        evals = m.log_decision.call_args[1]["policy_record"].evaluations
        release_evals = [e for e in evals if e.trigger == PolicyTrigger.ON_RELEASE]
        assert release_evals[0].effect == PolicyEffect.WARN


# ===========================================================================
# Existing behavior preserved
# ===========================================================================


class TestExistingBehaviorPreserved:
    async def test_tokens_still_streamed(self) -> None:
        from app.api.chat import _stream
        chunks: list[str] = []
        with _patch_policy_chat(tokens=["A", "B"]) as _:
            async for chunk in _stream(_make_conv(), "q", None, _UID):
                chunks.append(chunk)
        assert _event_types(chunks).count("token") == 2

    async def test_citations_still_emitted(self) -> None:
        from app.api.chat import _stream
        chunks: list[str] = []
        with _patch_policy_chat() as _:
            async for chunk in _stream(_make_conv(), "q", None, _UID):
                chunks.append(chunk)
        assert "citations" in _event_types(chunks)

    async def test_event_order_token_citations_done(self) -> None:
        from app.api.chat import _stream
        chunks: list[str] = []
        with _patch_policy_chat(tokens=["tok"]) as _:
            async for chunk in _stream(_make_conv(), "q", None, _UID):
                chunks.append(chunk)
        types = _event_types(chunks)
        assert types.index("token") < types.index("citations")
        assert types.index("citations") < types.index("done")

    async def test_ledger_failure_does_not_prevent_done(self) -> None:
        from app.api.chat import _stream
        chunks: list[str] = []
        with _patch_policy_chat() as m:
            m.log_decision.side_effect = RuntimeError("Firestore down")
            async for chunk in _stream(_make_conv(), "q", None, _UID):
                chunks.append(chunk)
        assert "done" in _event_types(chunks)

    async def test_embed_failure_skips_to_error(self) -> None:
        from app.api.chat import _stream
        chunks: list[str] = []
        with _patch_policy_chat() as m:
            m.embed_query.side_effect = RuntimeError("embed fail")
            async for chunk in _stream(_make_conv(), "q", None, _UID):
                chunks.append(chunk)
        assert "error" in _event_types(chunks)
        assert "done" not in _event_types(chunks)


# ===========================================================================
# Require ledger
# ===========================================================================


class TestRequireLedger:
    async def test_require_ledger_emits_done_when_ledger_ok(self) -> None:
        from app.api.chat import _stream
        chunks: list[str] = []
        with _patch_policy_chat(release_effect=PolicyEffect.REQUIRE_LEDGER) as _:
            async for chunk in _stream(_make_conv(), "q", None, _UID):
                chunks.append(chunk)
        assert "done" in _event_types(chunks)

    async def test_require_ledger_withholds_done_on_ledger_failure(self) -> None:
        from app.api.chat import _stream
        chunks: list[str] = []
        with _patch_policy_chat(release_effect=PolicyEffect.REQUIRE_LEDGER) as m:
            m.log_decision.side_effect = RuntimeError("Firestore down")
            async for chunk in _stream(_make_conv(), "q", None, _UID):
                chunks.append(chunk)
        assert "done" not in _event_types(chunks)
        assert "error" in _event_types(chunks)

    async def test_require_ledger_emits_policy_sse(self) -> None:
        from app.api.chat import _stream
        chunks: list[str] = []
        with _patch_policy_chat(
            release_effect=PolicyEffect.REQUIRE_LEDGER, release_message="Ledger required"
        ) as _:
            async for chunk in _stream(_make_conv(), "q", None, _UID):
                chunks.append(chunk)
        assert "policy" in _event_types(chunks)
