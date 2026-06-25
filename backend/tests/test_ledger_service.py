"""Unit tests for AI Decision Ledger service — repo mocked, no network calls."""
from __future__ import annotations

import hashlib
import uuid
from datetime import datetime, timezone
from unittest.mock import AsyncMock, patch

import pytest

from app.models.chunk import ChunkCitation
from app.models.ledger import (
    CachedCitation,
    DecisionEvent,
    DecisionKind,
    GroundingStatus,
    ModelParams,
    OutputRecord,
    PolicyEffect,
    PolicyEvaluation,
    PolicyRecord,
    PolicyTrigger,
    RetrievalParams,
    RetrievalRecord,
)
from app.repositories.ledger_repo import compute_entry_hash
from app.services.ledger import _GENESIS_HASH, log_decision
from app.services.llm import (
    LLM_MAX_OUTPUT_TOKENS,
    LLM_MODEL_NAME,
    LLM_TEMPERATURE,
    PROMPT_TEMPLATE_VERSION,
)

UTC = timezone.utc
_ORG = "uid_alice"
_CONV = "conv_001"
_UID = "uid_alice"
_MSG = "msg_asst_001"
_QUERY = "Can we cap liability at 6 months?"
_ANSWER = "Liability is typically capped at 12 months per standard terms."


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _citation(**kw: object) -> ChunkCitation:
    base: dict[str, object] = dict(
        doc_id="doc_001", original_filename="MSA.pdf",
        chunk_index=4, page_number=12,
        content="Liability clause text.", score=0.71,
    )
    base.update(kw)
    return ChunkCitation(**base)  # type: ignore[arg-type]


def _prev_entry(seq: int = 1) -> DecisionEvent:
    """Valid DecisionEvent to act as 'previous' ledger entry."""
    draft = DecisionEvent(
        id=f"prev_{seq}",
        org_id=_ORG,
        kind=DecisionKind.DECISION,
        sequence_no=seq,
        actor_uid=_UID,
        conversation_id=_CONV,
        message_id=f"msg_{seq:03d}",
        query="Previous query.",
        document_ids=[],
        retrieval=RetrievalRecord(
            params=RetrievalParams(top_k=5, score_threshold=0.3),
            citations=[],
        ),
        memory_used=[],
        model=ModelParams(
            name=LLM_MODEL_NAME, temperature=LLM_TEMPERATURE,
            max_output_tokens=LLM_MAX_OUTPUT_TOKENS,
            prompt_template_version=PROMPT_TEMPLATE_VERSION,
        ),
        policy=PolicyRecord(
            snapshot_id="default",
            evaluations=[
                PolicyEvaluation(
                    trigger=PolicyTrigger.ON_RELEASE,
                    effect=PolicyEffect.ALLOW,
                    policy_id="default-allow",
                )
            ],
        ),
        output=OutputRecord(
            answer_hash="sha256:prev",
            answer_ref=f"msg_{seq:03d}",
            sources_used=False,
            grounding=GroundingStatus(
                citations_above_threshold=0, top_score=0.0, disclaimer_emitted=True,
            ),
        ),
        prev_hash=_GENESIS_HASH,
        entry_hash="sha256:placeholder",
        created_at=datetime(2026, 6, 25, 6, 0, 0, tzinfo=UTC),
    )
    return draft.model_copy(update={"entry_hash": compute_entry_hash(draft)})


async def _call_log(**kw: object) -> None:
    base: dict[str, object] = dict(
        org_id=_ORG, conv_id=_CONV, actor_uid=_UID,
        message_id=_MSG, query=_QUERY,
        document_ids=["doc_001"], citations=[_citation()],
        accumulated_answer=_ANSWER, sources_used=True,
    )
    base.update(kw)
    await log_decision(**base)  # type: ignore[arg-type]


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------


@pytest.fixture
def mock_repo() -> tuple[AsyncMock, AsyncMock]:
    with (
        patch("app.services.ledger.get_latest_entry", new_callable=AsyncMock) as m_latest,
        patch("app.services.ledger.append_entry", new_callable=AsyncMock) as m_append,
    ):
        m_latest.return_value = None  # empty ledger by default
        yield m_latest, m_append  # type: ignore[misc]


# ===========================================================================
# append — called exactly once
# ===========================================================================


class TestLogDecisionAppend:
    async def test_appends_one_entry(self, mock_repo: tuple[AsyncMock, AsyncMock]) -> None:
        _, m_append = mock_repo
        await _call_log()
        m_append.assert_called_once()

    async def test_entry_is_decision_event(self, mock_repo: tuple[AsyncMock, AsyncMock]) -> None:
        _, m_append = mock_repo
        await _call_log()
        _org_id, entry = m_append.call_args[0]
        assert isinstance(entry, DecisionEvent)

    async def test_entry_kind_is_decision(self, mock_repo: tuple[AsyncMock, AsyncMock]) -> None:
        _, m_append = mock_repo
        await _call_log()
        _, entry = m_append.call_args[0]
        assert entry.kind == DecisionKind.DECISION

    async def test_org_id_forwarded(self, mock_repo: tuple[AsyncMock, AsyncMock]) -> None:
        _, m_append = mock_repo
        await _call_log(org_id="org_custom")
        org_id, entry = m_append.call_args[0]
        assert org_id == "org_custom"
        assert entry.org_id == "org_custom"

    async def test_entry_has_valid_uuid_id(self, mock_repo: tuple[AsyncMock, AsyncMock]) -> None:
        _, m_append = mock_repo
        await _call_log()
        _, entry = m_append.call_args[0]
        uuid.UUID(entry.id)  # raises if not valid UUID

    async def test_propagates_repo_exception(self, mock_repo: tuple[AsyncMock, AsyncMock]) -> None:
        _, m_append = mock_repo
        m_append.side_effect = RuntimeError("Firestore unavailable")
        with pytest.raises(RuntimeError, match="Firestore unavailable"):
            await _call_log()


# ===========================================================================
# hash chain
# ===========================================================================


class TestHashChain:
    async def test_first_entry_uses_genesis_hash(
        self, mock_repo: tuple[AsyncMock, AsyncMock]
    ) -> None:
        m_latest, m_append = mock_repo
        m_latest.return_value = None
        await _call_log()
        _, entry = m_append.call_args[0]
        assert entry.prev_hash == _GENESIS_HASH

    async def test_first_entry_sequence_no_is_one(
        self, mock_repo: tuple[AsyncMock, AsyncMock]
    ) -> None:
        m_latest, m_append = mock_repo
        m_latest.return_value = None
        await _call_log()
        _, entry = m_append.call_args[0]
        assert entry.sequence_no == 1

    async def test_chain_continues_from_previous_hash(
        self, mock_repo: tuple[AsyncMock, AsyncMock]
    ) -> None:
        m_latest, m_append = mock_repo
        prev = _prev_entry(seq=3)
        m_latest.return_value = prev
        await _call_log()
        _, entry = m_append.call_args[0]
        assert entry.prev_hash == prev.entry_hash

    async def test_sequence_no_increments_from_previous(
        self, mock_repo: tuple[AsyncMock, AsyncMock]
    ) -> None:
        m_latest, m_append = mock_repo
        prev = _prev_entry(seq=7)
        m_latest.return_value = prev
        await _call_log()
        _, entry = m_append.call_args[0]
        assert entry.sequence_no == 8

    async def test_entry_hash_matches_canonical_computation(
        self, mock_repo: tuple[AsyncMock, AsyncMock]
    ) -> None:
        _, m_append = mock_repo
        await _call_log()
        _, entry = m_append.call_args[0]
        assert entry.entry_hash == compute_entry_hash(entry)

    async def test_entry_hash_is_not_placeholder(
        self, mock_repo: tuple[AsyncMock, AsyncMock]
    ) -> None:
        _, m_append = mock_repo
        await _call_log()
        _, entry = m_append.call_args[0]
        assert entry.entry_hash != "sha256:placeholder"

    async def test_two_turns_chain_correctly(
        self, mock_repo: tuple[AsyncMock, AsyncMock]
    ) -> None:
        m_latest, m_append = mock_repo

        m_latest.return_value = None
        await _call_log(message_id="msg_001")
        _, entry1 = m_append.call_args[0]

        m_latest.return_value = entry1
        await _call_log(message_id="msg_002")
        _, entry2 = m_append.call_args[0]

        assert entry2.sequence_no == entry1.sequence_no + 1
        assert entry2.prev_hash == entry1.entry_hash

    async def test_different_prev_hash_produces_different_entry_hash(
        self, mock_repo: tuple[AsyncMock, AsyncMock]
    ) -> None:
        m_latest, m_append = mock_repo

        m_latest.return_value = _prev_entry(seq=1)
        await _call_log()
        _, entry_with_prev = m_append.call_args[0]

        m_latest.return_value = None
        await _call_log()
        _, entry_genesis = m_append.call_args[0]

        assert entry_with_prev.entry_hash != entry_genesis.entry_hash


# ===========================================================================
# field linkage
# ===========================================================================


class TestFieldLinkage:
    async def test_conv_id_linked(self, mock_repo: tuple[AsyncMock, AsyncMock]) -> None:
        _, m_append = mock_repo
        await _call_log(conv_id="conv_xyz")
        _, entry = m_append.call_args[0]
        assert entry.conversation_id == "conv_xyz"

    async def test_message_id_linked(self, mock_repo: tuple[AsyncMock, AsyncMock]) -> None:
        _, m_append = mock_repo
        await _call_log(message_id="msg_xyz")
        _, entry = m_append.call_args[0]
        assert entry.message_id == "msg_xyz"

    async def test_query_linked(self, mock_repo: tuple[AsyncMock, AsyncMock]) -> None:
        _, m_append = mock_repo
        await _call_log(query="Custom query text.")
        _, entry = m_append.call_args[0]
        assert entry.query == "Custom query text."

    async def test_document_ids_linked(self, mock_repo: tuple[AsyncMock, AsyncMock]) -> None:
        _, m_append = mock_repo
        await _call_log(document_ids=["doc_A", "doc_B"])
        _, entry = m_append.call_args[0]
        assert entry.document_ids == ["doc_A", "doc_B"]

    async def test_actor_uid_linked(self, mock_repo: tuple[AsyncMock, AsyncMock]) -> None:
        _, m_append = mock_repo
        await _call_log(actor_uid="uid_other")
        _, entry = m_append.call_args[0]
        assert entry.actor_uid == "uid_other"

    async def test_answer_ref_is_message_id(self, mock_repo: tuple[AsyncMock, AsyncMock]) -> None:
        _, m_append = mock_repo
        await _call_log(message_id="msg_ref_test")
        _, entry = m_append.call_args[0]
        assert entry.output.answer_ref == "msg_ref_test"

    async def test_answer_hash_is_sha256_of_answer(
        self, mock_repo: tuple[AsyncMock, AsyncMock]
    ) -> None:
        _, m_append = mock_repo
        answer = "The answer is 42."
        await _call_log(accumulated_answer=answer)
        _, entry = m_append.call_args[0]
        expected = "sha256:" + hashlib.sha256(answer.encode()).hexdigest()
        assert entry.output.answer_hash == expected

    async def test_model_name_from_llm_constants(
        self, mock_repo: tuple[AsyncMock, AsyncMock]
    ) -> None:
        _, m_append = mock_repo
        await _call_log()
        _, entry = m_append.call_args[0]
        assert entry.model.name == LLM_MODEL_NAME

    async def test_prompt_template_version_set(
        self, mock_repo: tuple[AsyncMock, AsyncMock]
    ) -> None:
        _, m_append = mock_repo
        await _call_log()
        _, entry = m_append.call_args[0]
        assert entry.model.prompt_template_version == PROMPT_TEMPLATE_VERSION

    async def test_memory_used_empty(self, mock_repo: tuple[AsyncMock, AsyncMock]) -> None:
        _, m_append = mock_repo
        await _call_log()
        _, entry = m_append.call_args[0]
        assert entry.memory_used == []


# ===========================================================================
# citation linkage
# ===========================================================================


class TestCitationLinkage:
    async def test_citation_count_matches(self, mock_repo: tuple[AsyncMock, AsyncMock]) -> None:
        _, m_append = mock_repo
        await _call_log(citations=[_citation(), _citation(chunk_index=5)])
        _, entry = m_append.call_args[0]
        assert len(entry.retrieval.citations) == 2

    async def test_citation_doc_id_preserved(
        self, mock_repo: tuple[AsyncMock, AsyncMock]
    ) -> None:
        _, m_append = mock_repo
        await _call_log(citations=[_citation(doc_id="doc_special")])
        _, entry = m_append.call_args[0]
        assert entry.retrieval.citations[0].doc_id == "doc_special"

    async def test_citation_filename_preserved(
        self, mock_repo: tuple[AsyncMock, AsyncMock]
    ) -> None:
        _, m_append = mock_repo
        await _call_log(citations=[_citation(original_filename="Contract.pdf")])
        _, entry = m_append.call_args[0]
        assert entry.retrieval.citations[0].original_filename == "Contract.pdf"

    async def test_citation_score_preserved(
        self, mock_repo: tuple[AsyncMock, AsyncMock]
    ) -> None:
        _, m_append = mock_repo
        await _call_log(citations=[_citation(score=0.85)])
        _, entry = m_append.call_args[0]
        assert entry.retrieval.citations[0].score == 0.85

    async def test_citation_page_number_preserved(
        self, mock_repo: tuple[AsyncMock, AsyncMock]
    ) -> None:
        _, m_append = mock_repo
        await _call_log(citations=[_citation(page_number=7)])
        _, entry = m_append.call_args[0]
        assert entry.retrieval.citations[0].page_number == 7

    async def test_citation_chunk_index_preserved(
        self, mock_repo: tuple[AsyncMock, AsyncMock]
    ) -> None:
        _, m_append = mock_repo
        await _call_log(citations=[_citation(chunk_index=11)])
        _, entry = m_append.call_args[0]
        assert entry.retrieval.citations[0].chunk_index == 11

    async def test_empty_citations(self, mock_repo: tuple[AsyncMock, AsyncMock]) -> None:
        _, m_append = mock_repo
        await _call_log(citations=[], sources_used=False)
        _, entry = m_append.call_args[0]
        assert entry.retrieval.citations == []

    async def test_cached_citation_type(self, mock_repo: tuple[AsyncMock, AsyncMock]) -> None:
        _, m_append = mock_repo
        await _call_log(citations=[_citation()])
        _, entry = m_append.call_args[0]
        assert isinstance(entry.retrieval.citations[0], CachedCitation)


# ===========================================================================
# grounding status
# ===========================================================================


class TestGroundingStatus:
    async def test_sources_used_true(self, mock_repo: tuple[AsyncMock, AsyncMock]) -> None:
        _, m_append = mock_repo
        await _call_log(citations=[_citation()], sources_used=True)
        _, entry = m_append.call_args[0]
        assert entry.output.sources_used is True

    async def test_sources_used_false(self, mock_repo: tuple[AsyncMock, AsyncMock]) -> None:
        _, m_append = mock_repo
        await _call_log(citations=[], sources_used=False)
        _, entry = m_append.call_args[0]
        assert entry.output.sources_used is False

    async def test_citations_above_threshold_count(
        self, mock_repo: tuple[AsyncMock, AsyncMock]
    ) -> None:
        _, m_append = mock_repo
        await _call_log(citations=[_citation(), _citation(chunk_index=5)])
        _, entry = m_append.call_args[0]
        assert entry.output.grounding.citations_above_threshold == 2

    async def test_top_score_is_max_citation_score(
        self, mock_repo: tuple[AsyncMock, AsyncMock]
    ) -> None:
        _, m_append = mock_repo
        await _call_log(
            citations=[_citation(score=0.5), _citation(score=0.9, chunk_index=5)],
            sources_used=True,
        )
        _, entry = m_append.call_args[0]
        assert entry.output.grounding.top_score == pytest.approx(0.9)

    async def test_top_score_zero_when_no_citations(
        self, mock_repo: tuple[AsyncMock, AsyncMock]
    ) -> None:
        _, m_append = mock_repo
        await _call_log(citations=[], sources_used=False)
        _, entry = m_append.call_args[0]
        assert entry.output.grounding.top_score == 0.0

    async def test_disclaimer_emitted_when_no_sources(
        self, mock_repo: tuple[AsyncMock, AsyncMock]
    ) -> None:
        _, m_append = mock_repo
        await _call_log(citations=[], sources_used=False)
        _, entry = m_append.call_args[0]
        assert entry.output.grounding.disclaimer_emitted is True

    async def test_disclaimer_not_emitted_when_sources_used(
        self, mock_repo: tuple[AsyncMock, AsyncMock]
    ) -> None:
        _, m_append = mock_repo
        await _call_log(citations=[_citation()], sources_used=True)
        _, entry = m_append.call_args[0]
        assert entry.output.grounding.disclaimer_emitted is False

    async def test_grounding_type(self, mock_repo: tuple[AsyncMock, AsyncMock]) -> None:
        _, m_append = mock_repo
        await _call_log()
        _, entry = m_append.call_args[0]
        assert isinstance(entry.output.grounding, GroundingStatus)
