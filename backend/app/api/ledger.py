"""Decision Timeline API — read-only ledger access.

Routes:
    GET /api/conversations/{conv_id}/decisions          → full timeline
    GET /api/conversations/{conv_id}/decisions/{id}    → single entry

Ownership validated against the conversation (404 for wrong owner or missing).
org_id is derived from the authenticated user's uid (personal org — uid == org_id)
until M6.2 adds the Organization layer.

No writes, no Any types, no business logic: pure fetch + serialize.
"""
from __future__ import annotations

import logging

from fastapi import APIRouter, Depends, HTTPException, status
from pydantic import BaseModel

from app.core.auth import get_current_user
from app.models.user import User
from app.repositories import ledger_repo
from app.services.conversations import get_conversation

_log = logging.getLogger(__name__)

router = APIRouter(
    prefix="/api/conversations/{conv_id}/decisions",
    tags=["ledger"],
)


# ---------------------------------------------------------------------------
# Response models
# ---------------------------------------------------------------------------


class LedgerEntryResponse(BaseModel):
    """Serialized ledger entry. The `kind` field discriminates the full shape.

    Common fields are always present. Kind-specific fields are None when absent.
    Clients should branch on `kind` in {decision, annotation, override}.
    """

    # --- common to all entry kinds ---
    id: str
    org_id: str
    kind: str
    sequence_no: int
    actor_uid: str
    conversation_id: str
    prev_hash: str
    entry_hash: str
    created_at: str

    # --- kind=decision ---
    message_id: str | None = None
    query: str | None = None
    document_ids: list[str] | None = None
    language: str | None = None
    retrieval: dict[str, object] | None = None
    memory_used: list[dict[str, object]] | None = None
    model: dict[str, object] | None = None
    policy: dict[str, object] | None = None
    output: dict[str, object] | None = None

    # --- kind=override ---
    # kind=annotation also uses decision_id
    decision_id: str | None = None
    approver: str | None = None
    reason: str | None = None
    previous_recommendation: str | None = None
    final_outcome: str | None = None
    disposition: str | None = None

    # --- kind=annotation ---
    original_hash: str | None = None
    note: str | None = None


class DecisionTimelineResponse(BaseModel):
    conversation_id: str
    entries: list[LedgerEntryResponse]
    total: int


# ---------------------------------------------------------------------------
# Internal helpers
# ---------------------------------------------------------------------------


def _to_response(entry: ledger_repo.LedgerEntry) -> LedgerEntryResponse:
    """Convert a domain ledger entry to its API response shape."""
    raw = entry.model_dump(mode="json")
    # created_at is serialized to ISO string by the field_serializer on the domain models
    return LedgerEntryResponse(
        id=str(raw["id"]),
        org_id=str(raw["org_id"]),
        kind=str(raw["kind"]),
        sequence_no=int(raw["sequence_no"]),
        actor_uid=str(raw["actor_uid"]),
        conversation_id=str(raw["conversation_id"]),
        prev_hash=str(raw["prev_hash"]),
        entry_hash=str(raw["entry_hash"]),
        created_at=str(raw["created_at"]),
        message_id=raw.get("message_id") and str(raw["message_id"]) or None,
        query=raw.get("query") and str(raw["query"]) or None,
        document_ids=raw.get("document_ids"),
        language=raw.get("language") and str(raw["language"]) or None,
        retrieval=raw.get("retrieval"),
        memory_used=raw.get("memory_used"),
        model=raw.get("model"),
        policy=raw.get("policy"),
        output=raw.get("output"),
        decision_id=raw.get("decision_id") and str(raw["decision_id"]) or None,
        approver=raw.get("approver") and str(raw["approver"]) or None,
        reason=raw.get("reason") and str(raw["reason"]) or None,
        previous_recommendation=(
            raw.get("previous_recommendation")
            and str(raw["previous_recommendation"])
            or None
        ),
        final_outcome=raw.get("final_outcome") and str(raw["final_outcome"]) or None,
        disposition=raw.get("disposition") and str(raw["disposition"]) or None,
        original_hash=raw.get("original_hash") and str(raw["original_hash"]) or None,
        note=raw.get("note") and str(raw["note"]) or None,
    )


# ---------------------------------------------------------------------------
# Routes
# ---------------------------------------------------------------------------


@router.get(
    "",
    response_model=DecisionTimelineResponse,
    summary="Get decision timeline for a conversation",
)
async def get_decision_timeline(
    conv_id: str,
    user: User = Depends(get_current_user),
) -> DecisionTimelineResponse:
    """Return all ledger entries for a conversation, ordered by sequence_no ascending.

    Returns 404 if the conversation does not exist or belongs to another user.
    Returns an empty entries list when no decisions have been logged yet.
    """
    # Ownership check — raises 404 for missing or wrong-owner conversation.
    get_conversation(conv_id, user.uid)

    # personal org: uid == org_id until M6.2 introduces Organization
    org_id = user.uid
    entries = await ledger_repo.get_timeline(org_id, conv_id)

    _log.info(
        "Decision timeline fetched: conv=%s uid=%s count=%d",
        conv_id, user.uid, len(entries),
    )
    return DecisionTimelineResponse(
        conversation_id=conv_id,
        entries=[_to_response(e) for e in entries],
        total=len(entries),
    )


@router.get(
    "/{decision_id}",
    response_model=LedgerEntryResponse,
    summary="Get a single ledger entry by ID",
)
async def get_decision(
    conv_id: str,
    decision_id: str,
    user: User = Depends(get_current_user),
) -> LedgerEntryResponse:
    """Return one ledger entry.

    Returns 404 if:
    - the conversation does not exist or belongs to another user
    - the entry does not exist in this org's ledger
    - the entry belongs to a different conversation (prevents cross-conversation access)
    """
    # Ownership check — raises 404 for missing or wrong-owner conversation.
    get_conversation(conv_id, user.uid)

    org_id = user.uid
    entry = await ledger_repo.get_entry(org_id, decision_id)

    if entry is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Decision not found.")

    # Guard: entry must belong to the requested conversation.
    if entry.conversation_id != conv_id:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Decision not found.")

    _log.info(
        "Decision fetched: conv=%s decision=%s uid=%s",
        conv_id, decision_id, user.uid,
    )
    return _to_response(entry)
