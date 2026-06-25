"""Tests for Decision Timeline API — services and repo mocked, no network calls."""
from __future__ import annotations

from collections.abc import Generator
from datetime import datetime, timezone
from unittest.mock import AsyncMock, patch

import pytest
from fastapi import HTTPException
from fastapi.testclient import TestClient

from app.core.auth import get_current_user
from app.main import create_app
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
from app.models.user import User
from app.repositories.ledger_repo import compute_entry_hash

UTC = timezone.utc
_T0 = datetime(2026, 6, 25, 6, 30, 0, tzinfo=UTC)

_USER = User(uid="uid_alice", email="alice@example.com", display_name=None, photo_url=None)
_OTHER = User(uid="uid_bob", email="bob@example.com", display_name=None, photo_url=None)
_CONV_ID = "conv_abc"
_ORG_ID = "uid_alice"  # personal org: uid == org_id


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


def _make_decision(
    entry_id: str = "e_001",
    seq: int = 1,
    conv_id: str = _CONV_ID,
    org_id: str = _ORG_ID,
) -> DecisionEvent:
    draft = DecisionEvent(
        id=entry_id,
        org_id=org_id,
        kind=DecisionKind.DECISION,
        sequence_no=seq,
        actor_uid="uid_alice",
        conversation_id=conv_id,
        message_id=f"msg_{seq:03d}",
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
    return draft.model_copy(update={"entry_hash": compute_entry_hash(draft)})


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------


@pytest.fixture
def client() -> Generator[TestClient, None, None]:
    app = create_app()
    app.dependency_overrides[get_current_user] = lambda: _USER
    with TestClient(app) as c:
        yield c


@pytest.fixture
def client_other() -> Generator[TestClient, None, None]:
    """Client authenticated as a different user."""
    app = create_app()
    app.dependency_overrides[get_current_user] = lambda: _OTHER
    with TestClient(app) as c:
        yield c


_TIMELINE_URL = f"/api/conversations/{_CONV_ID}/decisions"
_ENTRY_URL = f"/api/conversations/{_CONV_ID}/decisions/e_001"


# ---------------------------------------------------------------------------
# GET /api/conversations/{conv_id}/decisions  (timeline)
# ---------------------------------------------------------------------------


def test_timeline_returns_200(client: TestClient) -> None:
    decision = _make_decision()
    with (
        patch("app.api.ledger.get_conversation"),
        patch("app.api.ledger.ledger_repo.get_timeline", new=AsyncMock(return_value=[decision])),
    ):
        resp = client.get(_TIMELINE_URL)
    assert resp.status_code == 200


def test_timeline_response_shape(client: TestClient) -> None:
    decision = _make_decision()
    with (
        patch("app.api.ledger.get_conversation"),
        patch("app.api.ledger.ledger_repo.get_timeline", new=AsyncMock(return_value=[decision])),
    ):
        body = client.get(_TIMELINE_URL).json()
    assert body["conversation_id"] == _CONV_ID
    assert body["total"] == 1
    assert len(body["entries"]) == 1


def test_timeline_entry_serialization(client: TestClient) -> None:
    decision = _make_decision()
    with (
        patch("app.api.ledger.get_conversation"),
        patch("app.api.ledger.ledger_repo.get_timeline", new=AsyncMock(return_value=[decision])),
    ):
        body = client.get(_TIMELINE_URL).json()
    entry = body["entries"][0]
    assert entry["id"] == "e_001"
    assert entry["kind"] == "decision"
    assert entry["sequence_no"] == 1
    assert entry["conversation_id"] == _CONV_ID
    assert entry["org_id"] == _ORG_ID
    assert entry["created_at"].endswith("Z")
    assert entry["prev_hash"].startswith("sha256:")
    assert entry["entry_hash"].startswith("sha256:")
    assert entry["query"] == "Can we cap liability at 6 months?"
    assert entry["document_ids"] == ["doc_001"]
    assert isinstance(entry["retrieval"], dict)
    assert isinstance(entry["output"], dict)
    assert isinstance(entry["policy"], dict)
    assert isinstance(entry["model"], dict)


def test_timeline_empty(client: TestClient) -> None:
    with (
        patch("app.api.ledger.get_conversation"),
        patch("app.api.ledger.ledger_repo.get_timeline", new=AsyncMock(return_value=[])),
    ):
        body = client.get(_TIMELINE_URL).json()
    assert body["total"] == 0
    assert body["entries"] == []


def test_timeline_ordering_preserved(client: TestClient) -> None:
    """Entries returned in sequence_no ascending order (repo guarantees this)."""
    d1 = _make_decision(entry_id="e_001", seq=1)
    d2 = _make_decision(entry_id="e_002", seq=2)
    with (
        patch("app.api.ledger.get_conversation"),
        patch("app.api.ledger.ledger_repo.get_timeline", new=AsyncMock(return_value=[d1, d2])),
    ):
        body = client.get(_TIMELINE_URL).json()
    seqs = [e["sequence_no"] for e in body["entries"]]
    assert seqs == [1, 2]
    assert body["total"] == 2


def test_timeline_wrong_owner_returns_404(client_other: TestClient) -> None:
    with patch(
        "app.api.ledger.get_conversation",
        side_effect=HTTPException(status_code=404, detail="Conversation not found."),
    ):
        resp = client_other.get(_TIMELINE_URL)
    assert resp.status_code == 404


def test_timeline_missing_conversation_returns_404(client: TestClient) -> None:
    with patch(
        "app.api.ledger.get_conversation",
        side_effect=HTTPException(status_code=404, detail="Conversation not found."),
    ):
        resp = client.get(_TIMELINE_URL)
    assert resp.status_code == 404


def test_timeline_repo_failure_propagates(client: TestClient) -> None:
    with (
        patch("app.api.ledger.get_conversation"),
        patch(
            "app.api.ledger.ledger_repo.get_timeline",
            new=AsyncMock(side_effect=RuntimeError("Firestore unavailable")),
        ),
    ):
        with pytest.raises(RuntimeError, match="Firestore unavailable"):
            client.get(_TIMELINE_URL)


# ---------------------------------------------------------------------------
# GET /api/conversations/{conv_id}/decisions/{decision_id}
# ---------------------------------------------------------------------------


def test_get_decision_returns_200(client: TestClient) -> None:
    decision = _make_decision()
    with (
        patch("app.api.ledger.get_conversation"),
        patch("app.api.ledger.ledger_repo.get_entry", new=AsyncMock(return_value=decision)),
    ):
        resp = client.get(_ENTRY_URL)
    assert resp.status_code == 200


def test_get_decision_response_fields(client: TestClient) -> None:
    decision = _make_decision()
    with (
        patch("app.api.ledger.get_conversation"),
        patch("app.api.ledger.ledger_repo.get_entry", new=AsyncMock(return_value=decision)),
    ):
        entry = client.get(_ENTRY_URL).json()
    assert entry["id"] == "e_001"
    assert entry["kind"] == "decision"
    assert entry["conversation_id"] == _CONV_ID
    assert entry["created_at"].endswith("Z")


def test_get_decision_not_found_returns_404(client: TestClient) -> None:
    with (
        patch("app.api.ledger.get_conversation"),
        patch("app.api.ledger.ledger_repo.get_entry", new=AsyncMock(return_value=None)),
    ):
        resp = client.get(_ENTRY_URL)
    assert resp.status_code == 404
    assert resp.json()["detail"] == "Decision not found."


def test_get_decision_wrong_conversation_returns_404(client: TestClient) -> None:
    """Entry exists but belongs to a different conversation — must 404."""
    decision = _make_decision(conv_id="conv_other")
    with (
        patch("app.api.ledger.get_conversation"),
        patch("app.api.ledger.ledger_repo.get_entry", new=AsyncMock(return_value=decision)),
    ):
        resp = client.get(_ENTRY_URL)
    assert resp.status_code == 404
    assert resp.json()["detail"] == "Decision not found."


def test_get_decision_wrong_owner_returns_404(client_other: TestClient) -> None:
    with patch(
        "app.api.ledger.get_conversation",
        side_effect=HTTPException(status_code=404, detail="Conversation not found."),
    ):
        resp = client_other.get(_ENTRY_URL)
    assert resp.status_code == 404


def test_get_decision_repo_failure_propagates(client: TestClient) -> None:
    with (
        patch("app.api.ledger.get_conversation"),
        patch(
            "app.api.ledger.ledger_repo.get_entry",
            new=AsyncMock(side_effect=RuntimeError("Firestore unavailable")),
        ),
    ):
        with pytest.raises(RuntimeError, match="Firestore unavailable"):
            client.get(_ENTRY_URL)


# ---------------------------------------------------------------------------
# Serialization edge cases
# ---------------------------------------------------------------------------


def test_timestamp_ends_in_z(client: TestClient) -> None:
    """created_at must be Z-terminated ISO-8601 UTC."""
    decision = _make_decision()
    with (
        patch("app.api.ledger.get_conversation"),
        patch("app.api.ledger.ledger_repo.get_entry", new=AsyncMock(return_value=decision)),
    ):
        entry = client.get(_ENTRY_URL).json()
    assert entry["created_at"].endswith("Z"), f"Expected Z suffix: {entry['created_at']!r}"


def test_decision_kind_specific_fields_present(client: TestClient) -> None:
    """kind=decision must expose query, retrieval, model, policy, output."""
    decision = _make_decision()
    with (
        patch("app.api.ledger.get_conversation"),
        patch("app.api.ledger.ledger_repo.get_entry", new=AsyncMock(return_value=decision)),
    ):
        entry = client.get(_ENTRY_URL).json()
    for field in ("query", "retrieval", "model", "policy", "output", "message_id"):
        assert entry[field] is not None, f"Expected {field!r} present for kind=decision"


def test_override_fields_null_for_decision(client: TestClient) -> None:
    """Override-specific fields must be null for kind=decision entries."""
    decision = _make_decision()
    with (
        patch("app.api.ledger.get_conversation"),
        patch("app.api.ledger.ledger_repo.get_entry", new=AsyncMock(return_value=decision)),
    ):
        entry = client.get(_ENTRY_URL).json()
    for field in ("approver", "reason", "disposition", "final_outcome", "previous_recommendation"):
        assert entry[field] is None, f"Expected {field!r} None for kind=decision"
