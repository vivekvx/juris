"""Unit tests for AI Decision Ledger repository — Firestore mocked, no network calls."""
from __future__ import annotations

from collections.abc import Generator, Sequence
from datetime import datetime, timezone
from unittest.mock import MagicMock, patch

import pytest
from google.api_core.exceptions import AlreadyExists

from app.models.ledger import (
    CachedCitation,
    DecisionEvent,
    DecisionKind,
    GroundingStatus,
    HumanOverride,
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
from app.repositories.ledger_repo import (
    DuplicateEntryError,
    LedgerEntry,
    append_entry,
    canonical_for_hash,
    compute_entry_hash,
    get_entry,
    get_timeline,
    validate_chain,
)

UTC = timezone.utc
_T0 = datetime(2026, 6, 25, 6, 30, 0, tzinfo=UTC)

_ORG = "org_abc"
_CONV = "conv_001"


# ---------------------------------------------------------------------------
# Builder helpers
# ---------------------------------------------------------------------------


def _retrieval() -> RetrievalRecord:
    return RetrievalRecord(
        params=RetrievalParams(top_k=5, score_threshold=0.3),
        citations=[
            CachedCitation(
                doc_id="doc_001", chunk_index=4, page_number=12,
                score=0.71, original_filename="MSA.pdf",
            )
        ],
    )


def _model_params() -> ModelParams:
    return ModelParams(
        name="gemini-2.5-flash", temperature=0.3,
        max_output_tokens=2048, prompt_template_version="m6.1",
    )


def _policy() -> PolicyRecord:
    return PolicyRecord(
        snapshot_id="snap_001",
        evaluations=[
            PolicyEvaluation(
                trigger=PolicyTrigger.ON_RELEASE,
                effect=PolicyEffect.ALLOW,
                policy_id="pol_001",
            )
        ],
    )


def _output() -> OutputRecord:
    return OutputRecord(
        answer_hash="sha256:aabb",
        answer_ref="msg_001",
        sources_used=True,
        grounding=GroundingStatus(
            citations_above_threshold=3, top_score=0.71, disclaimer_emitted=False,
        ),
    )


def _make_decision(entry_id: str = "e_001", seq: int = 1, **kw: object) -> DecisionEvent:
    """Build a DecisionEvent with a real entry_hash computed from canonical form."""
    base: dict[str, object] = dict(
        id=entry_id,
        org_id=_ORG,
        kind=DecisionKind.DECISION,
        sequence_no=seq,
        actor_uid="uid_alice",
        conversation_id=_CONV,
        message_id="msg_001",
        query="Can we cap liability at 6 months?",
        document_ids=["doc_001"],
        retrieval=_retrieval(),
        memory_used=[],
        model=_model_params(),
        policy=_policy(),
        output=_output(),
        prev_hash="sha256:genesis",
        entry_hash="sha256:placeholder",
        created_at=_T0,
    )
    base.update(kw)
    draft = DecisionEvent(**base)  # type: ignore[arg-type]
    return draft.model_copy(update={"entry_hash": compute_entry_hash(draft)})


def _make_chain(n: int) -> list[LedgerEntry]:
    """Build a valid hash-chained sequence of n decision entries."""
    entries: list[LedgerEntry] = []
    prev_hash = "sha256:genesis"
    for i in range(n):
        seq = i + 1
        draft = DecisionEvent(
            id=f"e_{seq:03d}",
            org_id=_ORG,
            kind=DecisionKind.DECISION,
            sequence_no=seq,
            actor_uid="uid_alice",
            conversation_id=_CONV,
            message_id=f"msg_{seq:03d}",
            query=f"Query {seq}",
            document_ids=["doc_001"],
            retrieval=_retrieval(),
            memory_used=[],
            model=_model_params(),
            policy=_policy(),
            output=_output(),
            prev_hash=prev_hash,
            entry_hash="sha256:placeholder",
            created_at=_T0,
        )
        real_hash = compute_entry_hash(draft)
        entry = draft.model_copy(update={"entry_hash": real_hash})
        entries.append(entry)
        prev_hash = real_hash
    return entries


@pytest.fixture
def mock_db() -> Generator[MagicMock, None, None]:
    with patch("app.repositories.ledger_repo.get_firestore_client") as mock_get:
        mock_client = MagicMock()
        mock_get.return_value = mock_client
        yield mock_client


def _make_ref(mock_db: MagicMock) -> MagicMock:
    ref = MagicMock()
    (
        mock_db
        .collection.return_value
        .document.return_value
        .collection.return_value
        .document.return_value
    ) = ref
    return ref


def _make_snap(data: dict[str, object] | None, exists: bool = True) -> MagicMock:
    snap = MagicMock()
    snap.exists = exists
    snap.to_dict.return_value = data
    return snap


# ===========================================================================
# canonical_for_hash — pure
# ===========================================================================


class TestCanonicalForHash:
    def test_excludes_entry_hash(self) -> None:
        entry = _make_decision()
        assert "entry_hash" not in canonical_for_hash(entry)

    def test_includes_prev_hash(self) -> None:
        entry = _make_decision()
        assert "prev_hash" in canonical_for_hash(entry)

    def test_deterministic(self) -> None:
        entry = _make_decision()
        assert canonical_for_hash(entry) == canonical_for_hash(entry)

    def test_different_entries_differ(self) -> None:
        a = _make_decision(entry_id="e_001")
        b = _make_decision(entry_id="e_002")
        assert canonical_for_hash(a) != canonical_for_hash(b)

    def test_sorted_keys(self) -> None:
        import json
        entry = _make_decision()
        parsed = json.loads(canonical_for_hash(entry))
        keys = list(parsed.keys())
        assert keys == sorted(keys)


# ===========================================================================
# compute_entry_hash — pure
# ===========================================================================


class TestComputeEntryHash:
    def test_returns_sha256_prefix(self) -> None:
        h = compute_entry_hash(_make_decision())
        assert h.startswith("sha256:")

    def test_hex_length(self) -> None:
        h = compute_entry_hash(_make_decision())
        assert len(h) == len("sha256:") + 64

    def test_deterministic(self) -> None:
        entry = _make_decision()
        assert compute_entry_hash(entry) == compute_entry_hash(entry)

    def test_different_ids_differ(self) -> None:
        a = _make_decision(entry_id="e_001")
        b = _make_decision(entry_id="e_002")
        assert compute_entry_hash(a) != compute_entry_hash(b)

    def test_different_prev_hash_differs(self) -> None:
        a = _make_decision(prev_hash="sha256:aaa")
        b = _make_decision(prev_hash="sha256:bbb")
        assert compute_entry_hash(a) != compute_entry_hash(b)


# ===========================================================================
# validate_chain — pure
# ===========================================================================


class TestValidateChain:
    def test_empty_chain_is_valid(self) -> None:
        ok, errs = validate_chain([])
        assert ok is True
        assert errs == []

    def test_single_entry_valid(self) -> None:
        ok, errs = validate_chain(_make_chain(1))
        assert ok is True
        assert errs == []

    def test_three_entry_chain_valid(self) -> None:
        ok, errs = validate_chain(_make_chain(3))
        assert ok is True
        assert errs == []

    def test_tampered_entry_hash_detected(self) -> None:
        chain = _make_chain(2)
        tampered = chain[0].model_copy(update={"entry_hash": "sha256:tampered"})
        ok, errs = validate_chain([tampered, chain[1]])
        assert ok is False
        assert len(errs) >= 1

    def test_invalid_prev_hash_detected(self) -> None:
        chain = _make_chain(2)
        # Break chain link: recompute entry_hash so self-check passes, only link breaks.
        broken = chain[1].model_copy(update={"prev_hash": "sha256:wrong"})
        broken = broken.model_copy(update={"entry_hash": compute_entry_hash(broken)})
        ok, errs = validate_chain([chain[0], broken])
        assert ok is False
        assert any("prev_hash" in e for e in errs)

    def test_unordered_input_still_validates(self) -> None:
        chain = _make_chain(3)
        ok, errs = validate_chain(list(reversed(chain)))
        assert ok is True
        assert errs == []

    def test_multiple_errors_reported(self) -> None:
        chain = _make_chain(3)
        bad0 = chain[0].model_copy(update={"entry_hash": "sha256:bad0"})
        bad1 = chain[1].model_copy(update={"entry_hash": "sha256:bad1"})
        _, errs = validate_chain([bad0, bad1, chain[2]])
        assert len(errs) >= 2

    def test_errors_contain_entry_ids(self) -> None:
        chain = _make_chain(1)
        tampered = chain[0].model_copy(update={"entry_hash": "sha256:bad"})
        _, errs = validate_chain([tampered])
        assert any(chain[0].id in e for e in errs)


# ===========================================================================
# append_entry
# ===========================================================================


class TestAppendEntry:
    async def test_success_calls_create(self, mock_db: MagicMock) -> None:
        ref = _make_ref(mock_db)
        await append_entry(_ORG, _make_decision())
        ref.create.assert_called_once()

    async def test_create_receives_serialized_dict(self, mock_db: MagicMock) -> None:
        ref = _make_ref(mock_db)
        entry = _make_decision()
        await append_entry(_ORG, entry)
        call_args = ref.create.call_args[0][0]
        assert call_args["id"] == entry.id
        assert call_args["kind"] == "decision"
        assert call_args["org_id"] == _ORG
        assert call_args["sequence_no"] == entry.sequence_no

    async def test_duplicate_id_raises_duplicate_entry_error(self, mock_db: MagicMock) -> None:
        ref = _make_ref(mock_db)
        ref.create.side_effect = AlreadyExists("already exists")
        with pytest.raises(DuplicateEntryError):
            await append_entry(_ORG, _make_decision())

    async def test_duplicate_error_message_contains_entry_id(self, mock_db: MagicMock) -> None:
        ref = _make_ref(mock_db)
        ref.create.side_effect = AlreadyExists("already exists")
        with pytest.raises(DuplicateEntryError, match="e_dup"):
            await append_entry(_ORG, _make_decision(entry_id="e_dup"))

    async def test_created_at_serialized_with_z_suffix(self, mock_db: MagicMock) -> None:
        ref = _make_ref(mock_db)
        await append_entry(_ORG, _make_decision())
        call_args = ref.create.call_args[0][0]
        assert call_args["created_at"].endswith("Z")
        assert "+00:00" not in call_args["created_at"]

    async def test_correct_collection_path(self, mock_db: MagicMock) -> None:
        _make_ref(mock_db)
        entry = _make_decision()
        await append_entry(_ORG, entry)
        mock_db.collection.assert_called_with("organizations")
        mock_db.collection.return_value.document.assert_called_with(_ORG)
        (
            mock_db.collection.return_value.document.return_value
            .collection.assert_called_with("ledger")
        )
        (
            mock_db.collection.return_value.document.return_value
            .collection.return_value.document.assert_called_with(entry.id)
        )

    async def test_append_override_entry(self, mock_db: MagicMock) -> None:
        ref = _make_ref(mock_db)
        # Build a valid override with correct entry_hash.
        override_draft = HumanOverride(
            id="ov_001", org_id=_ORG, kind=DecisionKind.OVERRIDE,
            sequence_no=2, actor_uid="uid_bob", conversation_id=_CONV,
            decision_id="e_001", approver="uid_bob",
            reason="Client confirmed.", previous_recommendation="sha256:aaa",
            final_outcome="12-month cap.", disposition=OverrideDisposition.REPLACED,
            prev_hash="sha256:aaa", entry_hash="sha256:placeholder",
            created_at=_T0,
        )
        override = override_draft.model_copy(
            update={"entry_hash": compute_entry_hash(override_draft)}
        )
        await append_entry(_ORG, override)
        call_args = ref.create.call_args[0][0]
        assert call_args["kind"] == "override"
        assert call_args["decision_id"] == "e_001"


# ===========================================================================
# get_entry
# ===========================================================================


class TestGetEntry:
    async def test_returns_decision_event(self, mock_db: MagicMock) -> None:
        entry = _make_decision()
        ref = _make_ref(mock_db)
        ref.get.return_value = _make_snap(entry.model_dump(mode="json"))
        result = await get_entry(_ORG, entry.id)
        assert isinstance(result, DecisionEvent)
        assert result.id == entry.id

    async def test_returns_none_when_not_found(self, mock_db: MagicMock) -> None:
        ref = _make_ref(mock_db)
        ref.get.return_value = _make_snap(None, exists=False)
        result = await get_entry(_ORG, "missing_id")
        assert result is None

    async def test_returns_none_when_snap_data_is_none(self, mock_db: MagicMock) -> None:
        ref = _make_ref(mock_db)
        snap = MagicMock()
        snap.exists = True
        snap.to_dict.return_value = None
        ref.get.return_value = snap
        result = await get_entry(_ORG, "ghost_id")
        assert result is None

    async def test_correct_document_id_queried(self, mock_db: MagicMock) -> None:
        entry = _make_decision(entry_id="e_target")
        ref = _make_ref(mock_db)
        ref.get.return_value = _make_snap(entry.model_dump(mode="json"))
        await get_entry(_ORG, "e_target")
        (
            mock_db.collection.return_value.document.return_value
            .collection.return_value.document.assert_called_with("e_target")
        )

    async def test_deserializes_kind(self, mock_db: MagicMock) -> None:
        entry = _make_decision()
        ref = _make_ref(mock_db)
        ref.get.return_value = _make_snap(entry.model_dump(mode="json"))
        result = await get_entry(_ORG, entry.id)
        assert result is not None
        assert result.kind == DecisionKind.DECISION

    async def test_roundtrip_preserves_all_fields(self, mock_db: MagicMock) -> None:
        entry = _make_decision(entry_id="e_rt", seq=42)
        ref = _make_ref(mock_db)
        ref.get.return_value = _make_snap(entry.model_dump(mode="json"))
        result = await get_entry(_ORG, "e_rt")
        assert result is not None
        assert result.sequence_no == 42
        assert result.entry_hash == entry.entry_hash
        assert result.prev_hash == entry.prev_hash


# ===========================================================================
# get_timeline
# ===========================================================================


class TestGetTimeline:
    def _setup_stream(self, mock_db: MagicMock, entries: Sequence[LedgerEntry]) -> None:
        snaps = [_make_snap(e.model_dump(mode="json")) for e in entries]
        (
            mock_db
            .collection.return_value
            .document.return_value
            .collection.return_value
            .where.return_value
            .order_by.return_value
            .stream.return_value
        ) = iter(snaps)

    async def test_empty_timeline(self, mock_db: MagicMock) -> None:
        self._setup_stream(mock_db, [])
        result = await get_timeline(_ORG, _CONV)
        assert result == []

    async def test_single_entry(self, mock_db: MagicMock) -> None:
        [e] = _make_chain(1)
        self._setup_stream(mock_db, [e])
        result = await get_timeline(_ORG, _CONV)
        assert len(result) == 1
        assert result[0].id == e.id

    async def test_multiple_entries_returned(self, mock_db: MagicMock) -> None:
        chain = _make_chain(3)
        self._setup_stream(mock_db, chain)
        result = await get_timeline(_ORG, _CONV)
        assert len(result) == 3

    async def test_ordering_preserved(self, mock_db: MagicMock) -> None:
        chain = _make_chain(4)
        self._setup_stream(mock_db, chain)
        result = await get_timeline(_ORG, _CONV)
        seq_nos = [e.sequence_no for e in result]
        assert seq_nos == sorted(seq_nos)

    async def test_filters_by_conversation_id(self, mock_db: MagicMock) -> None:
        self._setup_stream(mock_db, _make_chain(1))
        await get_timeline(_ORG, _CONV)
        (
            mock_db.collection.return_value.document.return_value
            .collection.return_value
            .where.assert_called_with("conversation_id", "==", _CONV)
        )

    async def test_skips_malformed_entry(self, mock_db: MagicMock) -> None:
        good = _make_decision(entry_id="e_good")
        (
            mock_db
            .collection.return_value
            .document.return_value
            .collection.return_value
            .where.return_value
            .order_by.return_value
            .stream.return_value
        ) = iter([
            _make_snap({"kind": "unknown_kind", "id": "e_bad"}),
            _make_snap(good.model_dump(mode="json")),
        ])
        result = await get_timeline(_ORG, _CONV)
        assert len(result) == 1
        assert result[0].id == "e_good"

    async def test_results_are_correct_type(self, mock_db: MagicMock) -> None:
        chain = _make_chain(2)
        self._setup_stream(mock_db, chain)
        result = await get_timeline(_ORG, _CONV)
        assert all(isinstance(e, DecisionEvent) for e in result)
