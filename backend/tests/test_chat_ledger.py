"""Integration tests: _stream pipeline ledger wiring — all external deps mocked."""
from __future__ import annotations

import contextlib
from collections.abc import AsyncGenerator, Generator
from unittest.mock import AsyncMock, MagicMock, patch


from datetime import datetime, timezone

from app.models.chunk import ChunkCitation
from app.models.conversation import Conversation, Message

_T0 = datetime(2026, 6, 25, 6, 0, 0, tzinfo=timezone.utc)

# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

_UID = "uid_test"
_CONV_ID = "conv_001"
_MSG_ID = "msg_asst_001"


def _make_conv(conv_id: str = _CONV_ID) -> Conversation:
    return Conversation(
        id=conv_id,
        owner_uid=_UID,
        title="Test conv",
        title_generated=True,
        document_ids=["doc_001"],
        created_at=_T0,
        updated_at=_T0,
    )


def _citation(**kw: object) -> ChunkCitation:
    base: dict[str, object] = dict(
        doc_id="doc_001", original_filename="MSA.pdf",
        chunk_index=4, page_number=12,
        content="Relevant clause.", score=0.75,
    )
    base.update(kw)
    return ChunkCitation(**base)  # type: ignore[arg-type]


def _make_message(role: str = "user") -> Message:
    return Message(
        id="msg_user_001", conversation_id=_CONV_ID,
        uid=_UID, role=role, content="Hello",
        created_at=_T0,
    )


def _event_types(chunks: list[str]) -> list[str]:
    types: list[str] = []
    for chunk in chunks:
        for line in chunk.strip().split("\n"):
            if line.startswith("event: "):
                types.append(line[7:])
    return types


# ---------------------------------------------------------------------------
# Patch context manager
# ---------------------------------------------------------------------------


class _ChatMocks:
    list_messages: MagicMock
    embed_query: AsyncMock
    create_message: MagicMock
    retrieve: AsyncMock
    build_context: MagicMock
    create_assistant_message: MagicMock
    stream_response: AsyncMock
    log_decision: AsyncMock


@contextlib.contextmanager
def _patch_chat(
    tokens: list[str] | None = None,
    citations: list[ChunkCitation] | None = None,
    stream_raises: Exception | None = None,
) -> Generator[_ChatMocks, None, None]:
    mocks = _ChatMocks()

    async def _fake_stream(
        history: object, context: object, content: object
    ) -> AsyncGenerator[str, None]:
        if stream_raises is not None:
            raise stream_raises
        for t in (tokens or ["Hello", " world"]):
            yield t

    asst_msg = MagicMock()
    asst_msg.id = _MSG_ID

    with (
        patch("app.api.chat.list_messages", return_value=[_make_message()]) as p1,
        patch(
            "app.api.chat.embed_query",
            new_callable=AsyncMock,
            return_value=[0.1] * 768,
        ) as p2,
        patch("app.api.chat.create_message") as p3,
        patch(
            "app.api.chat.retrieve",
            new_callable=AsyncMock,
            return_value=citations or [],
        ) as p4,
        patch("app.api.chat.build_context", return_value="ctx") as p5,
        patch("app.api.chat.create_assistant_message", return_value=asst_msg) as p6,
        patch("app.api.chat.stream_response", side_effect=_fake_stream) as p7,
        patch("app.api.chat.log_decision", new_callable=AsyncMock) as p8,
    ):
        mocks.list_messages = p1
        mocks.embed_query = p2
        mocks.create_message = p3
        mocks.retrieve = p4
        mocks.build_context = p5
        mocks.create_assistant_message = p6
        mocks.stream_response = p7
        mocks.log_decision = p8
        yield mocks


# ===========================================================================
# Successful response → one ledger entry
# ===========================================================================


class TestSuccessfulResponse:
    async def test_log_decision_called_once(self) -> None:
        from app.api.chat import _stream

        with _patch_chat() as m:
            async for _ in _stream(_make_conv(), "My query", None, _UID):
                pass
            m.log_decision.assert_called_once()

    async def test_log_decision_receives_correct_org_id(self) -> None:
        from app.api.chat import _stream

        with _patch_chat() as m:
            async for _ in _stream(_make_conv(), "My query", None, _UID):
                pass
            kwargs = m.log_decision.call_args[1]
            assert kwargs["org_id"] == _UID

    async def test_log_decision_receives_correct_conv_id(self) -> None:
        from app.api.chat import _stream

        with _patch_chat() as m:
            async for _ in _stream(_make_conv(_CONV_ID), "My query", None, _UID):
                pass
            kwargs = m.log_decision.call_args[1]
            assert kwargs["conv_id"] == _CONV_ID

    async def test_log_decision_receives_actor_uid(self) -> None:
        from app.api.chat import _stream

        with _patch_chat() as m:
            async for _ in _stream(_make_conv(), "My query", None, _UID):
                pass
            kwargs = m.log_decision.call_args[1]
            assert kwargs["actor_uid"] == _UID

    async def test_log_decision_receives_message_id(self) -> None:
        from app.api.chat import _stream

        with _patch_chat() as m:
            async for _ in _stream(_make_conv(), "My query", None, _UID):
                pass
            kwargs = m.log_decision.call_args[1]
            assert kwargs["message_id"] == _MSG_ID

    async def test_log_decision_receives_query(self) -> None:
        from app.api.chat import _stream

        with _patch_chat() as m:
            async for _ in _stream(_make_conv(), "contract question", None, _UID):
                pass
            kwargs = m.log_decision.call_args[1]
            assert kwargs["query"] == "contract question"

    async def test_log_decision_receives_accumulated_answer(self) -> None:
        from app.api.chat import _stream

        with _patch_chat(tokens=["Part", "A", " PartB"]) as m:
            async for _ in _stream(_make_conv(), "q", None, _UID):
                pass
            kwargs = m.log_decision.call_args[1]
            assert kwargs["accumulated_answer"] == "PartA PartB"

    async def test_done_event_emitted_after_ledger(self) -> None:
        from app.api.chat import _stream

        chunks: list[str] = []
        with _patch_chat() as _:
            async for chunk in _stream(_make_conv(), "q", None, _UID):
                chunks.append(chunk)
        assert "done" in _event_types(chunks)


# ===========================================================================
# Citation linkage
# ===========================================================================


class TestCitationLinkage:
    async def test_citations_forwarded_to_log_decision(self) -> None:
        from app.api.chat import _stream

        cits = [_citation(doc_id="doc_X")]
        with _patch_chat(citations=cits) as m:
            async for _ in _stream(_make_conv(), "q", None, _UID):
                pass
            kwargs = m.log_decision.call_args[1]
            assert kwargs["citations"] == cits

    async def test_sources_used_true_when_citations_present(self) -> None:
        from app.api.chat import _stream

        with _patch_chat(citations=[_citation()]) as m:
            async for _ in _stream(_make_conv(), "q", None, _UID):
                pass
            kwargs = m.log_decision.call_args[1]
            assert kwargs["sources_used"] is True

    async def test_sources_used_false_when_no_citations(self) -> None:
        from app.api.chat import _stream

        with _patch_chat(citations=[]) as m:
            async for _ in _stream(_make_conv(), "q", None, _UID):
                pass
            kwargs = m.log_decision.call_args[1]
            assert kwargs["sources_used"] is False

    async def test_document_ids_from_conv(self) -> None:
        from app.api.chat import _stream

        conv = _make_conv().model_copy(update={"document_ids": ["doc_A", "doc_B"]})
        with _patch_chat() as m:
            async for _ in _stream(conv, "q", None, _UID):
                pass
            kwargs = m.log_decision.call_args[1]
            assert kwargs["document_ids"] == ["doc_A", "doc_B"]

    async def test_request_doc_ids_override_conv_doc_ids(self) -> None:
        from app.api.chat import _stream

        conv = _make_conv().model_copy(update={"document_ids": ["conv_doc"]})
        with _patch_chat() as m:
            async for _ in _stream(conv, "q", ["req_doc"], _UID):
                pass
            kwargs = m.log_decision.call_args[1]
            assert kwargs["document_ids"] == ["req_doc"]


# ===========================================================================
# Streaming failure → no ledger entry
# ===========================================================================


class TestStreamingFailure:
    async def test_llm_error_does_not_call_log_decision(self) -> None:
        from app.api.chat import _stream

        with _patch_chat(stream_raises=RuntimeError("LLM down")) as m:
            async for _ in _stream(_make_conv(), "q", None, _UID):
                pass
            m.log_decision.assert_not_called()

    async def test_llm_error_emits_error_sse(self) -> None:
        from app.api.chat import _stream

        chunks: list[str] = []
        with _patch_chat(stream_raises=RuntimeError("LLM down")) as _:
            async for chunk in _stream(_make_conv(), "q", None, _UID):
                chunks.append(chunk)
        types = _event_types(chunks)
        assert "error" in types
        assert "done" not in types

    async def test_embed_failure_does_not_call_log_decision(self) -> None:
        from app.api.chat import _stream

        with _patch_chat() as m:
            m.embed_query.side_effect = RuntimeError("embed fail")
            async for _ in _stream(_make_conv(), "q", None, _UID):
                pass
            m.log_decision.assert_not_called()


# ===========================================================================
# Ledger failure is graceful
# ===========================================================================


class TestLedgerFailureGraceful:
    async def test_ledger_exception_does_not_prevent_done_event(self) -> None:
        from app.api.chat import _stream

        chunks: list[str] = []
        with _patch_chat() as m:
            m.log_decision.side_effect = RuntimeError("Firestore down")
            async for chunk in _stream(_make_conv(), "q", None, _UID):
                chunks.append(chunk)
        assert "done" in _event_types(chunks)

    async def test_ledger_exception_does_not_emit_error_event(self) -> None:
        from app.api.chat import _stream

        chunks: list[str] = []
        with _patch_chat() as m:
            m.log_decision.side_effect = RuntimeError("Firestore down")
            async for chunk in _stream(_make_conv(), "q", None, _UID):
                chunks.append(chunk)
        assert "error" not in _event_types(chunks)


# ===========================================================================
# Multiple conversation turns
# ===========================================================================


class TestMultipleTurns:
    async def test_each_turn_calls_log_decision_once(self) -> None:
        from app.api.chat import _stream

        with _patch_chat() as m:
            async for _ in _stream(_make_conv(), "turn 1", None, _UID):
                pass
            assert m.log_decision.call_count == 1

            async for _ in _stream(_make_conv(), "turn 2", None, _UID):
                pass
            assert m.log_decision.call_count == 2

    async def test_each_turn_uses_unique_query(self) -> None:
        from app.api.chat import _stream

        queries: list[str] = []
        with _patch_chat() as m:
            for q in ["first question", "second question"]:
                async for _ in _stream(_make_conv(), q, None, _UID):
                    pass
            for call in m.log_decision.call_args_list:
                queries.append(call[1]["query"])
        assert queries == ["first question", "second question"]
