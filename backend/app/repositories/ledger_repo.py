"""AI Decision Ledger repository — append-only, hash-chained Firestore persistence.

Collection path: organizations/{org_id}/ledger/{entry_id}
Writes use .create() (not .set()), which fails atomically on duplicate IDs.
Hash helpers are pure functions — no I/O — so callers can compute and verify
entry_hash before calling append_entry.
"""
from __future__ import annotations

import asyncio
import hashlib
import json
import logging
from collections.abc import Sequence

from google.api_core.exceptions import AlreadyExists
from google.cloud.firestore import Query

from app.core.firebase import get_firestore_client
from app.models.ledger import DecisionAnnotation, DecisionEvent, DecisionKind, HumanOverride

_log = logging.getLogger(__name__)

_ORGS = "organizations"
_LEDGER = "ledger"

LedgerEntry = DecisionEvent | HumanOverride | DecisionAnnotation


class DuplicateEntryError(Exception):
    """Raised when an entry_id already exists in the org ledger."""


# ---------------------------------------------------------------------------
# Serialization
# ---------------------------------------------------------------------------


def _entry_to_dict(entry: LedgerEntry) -> dict[str, object]:
    return entry.model_dump(mode="json")


def _dict_to_entry(data: dict[str, object]) -> LedgerEntry:
    kind_str = data.get("kind")
    if kind_str == DecisionKind.DECISION:
        return DecisionEvent.model_validate(data)
    if kind_str == DecisionKind.OVERRIDE:
        return HumanOverride.model_validate(data)
    if kind_str == DecisionKind.ANNOTATION:
        return DecisionAnnotation.model_validate(data)
    raise ValueError(f"Unknown ledger entry kind: {kind_str!r}")


# ---------------------------------------------------------------------------
# Hash-chain helpers (pure, no I/O)
# ---------------------------------------------------------------------------


def canonical_for_hash(entry: LedgerEntry) -> str:
    """Canonical JSON of entry with entry_hash excluded, deterministic key order."""
    data = entry.model_dump(mode="json")
    data.pop("entry_hash", None)
    return json.dumps(data, sort_keys=True, separators=(",", ":"))


def compute_entry_hash(entry: LedgerEntry) -> str:
    """SHA-256 over canonical entry form (entry_hash excluded). Returns 'sha256:<hex>'."""
    digest = hashlib.sha256(canonical_for_hash(entry).encode()).hexdigest()
    return f"sha256:{digest}"


def validate_chain(entries: Sequence[LedgerEntry]) -> tuple[bool, list[str]]:
    """Verify hash-chain integrity over a list of ledger entries.

    Entries are sorted by sequence_no internally. Checks:
    1. Each stored entry_hash matches the recomputed hash.
    2. Each entry's prev_hash matches the preceding entry's entry_hash.

    Returns (is_valid, errors). Errors is empty when valid.
    """
    errors: list[str] = []
    ordered = sorted(entries, key=lambda e: e.sequence_no)

    for i, entry in enumerate(ordered):
        expected = compute_entry_hash(entry)
        if entry.entry_hash != expected:
            errors.append(
                f"entry {entry.id} seq={entry.sequence_no}: "
                f"stored hash {entry.entry_hash!r} != computed {expected!r}"
            )
        if i > 0:
            prev = ordered[i - 1]
            if entry.prev_hash != prev.entry_hash:
                errors.append(
                    f"entry {entry.id} seq={entry.sequence_no}: "
                    f"prev_hash {entry.prev_hash!r} != preceding entry_hash {prev.entry_hash!r}"
                )

    return (len(errors) == 0, errors)


# ---------------------------------------------------------------------------
# Firestore CRUD
# ---------------------------------------------------------------------------


async def append_entry(org_id: str, entry: LedgerEntry) -> None:
    """Append one ledger entry. Raises DuplicateEntryError if the entry_id already exists.

    Uses Firestore .create() so the write fails atomically on collision — no update path exists.
    """
    db = get_firestore_client()
    ref = (
        db.collection(_ORGS)
        .document(org_id)
        .collection(_LEDGER)
        .document(entry.id)
    )
    try:
        await asyncio.to_thread(ref.create, _entry_to_dict(entry))
    except AlreadyExists:
        raise DuplicateEntryError(
            f"Ledger entry {entry.id!r} already exists in org {org_id!r}"
        )
    _log.info(
        "Ledger entry appended: org=%s id=%s kind=%s seq=%s",
        org_id, entry.id, entry.kind, entry.sequence_no,
    )


async def get_entry(org_id: str, decision_id: str) -> LedgerEntry | None:
    """Fetch a single ledger entry by ID. Returns None if not found."""
    db = get_firestore_client()
    ref = (
        db.collection(_ORGS)
        .document(org_id)
        .collection(_LEDGER)
        .document(decision_id)
    )
    snap = await asyncio.to_thread(ref.get)
    if not snap.exists:
        return None
    data = snap.to_dict()
    if data is None:
        return None
    return _dict_to_entry(data)


async def get_latest_entry(org_id: str) -> LedgerEntry | None:
    """Entry with the highest sequence_no for org_id. None if ledger is empty."""
    db = get_firestore_client()

    def _query() -> LedgerEntry | None:
        snaps = list(
            db.collection(_ORGS)
            .document(org_id)
            .collection(_LEDGER)
            .order_by("sequence_no", direction=Query.DESCENDING)
            .limit(1)
            .stream()
        )
        if not snaps:
            return None
        data = snaps[0].to_dict()
        if data is None:
            return None
        try:
            return _dict_to_entry(data)
        except Exception:
            _log.warning("Malformed latest ledger entry for org %s", org_id)
            return None

    return await asyncio.to_thread(_query)


async def get_timeline(org_id: str, conversation_id: str) -> list[LedgerEntry]:
    """All ledger entries for a conversation, ordered by sequence_no ascending."""
    db = get_firestore_client()

    def _query() -> list[LedgerEntry]:
        snaps = (
            db.collection(_ORGS)
            .document(org_id)
            .collection(_LEDGER)
            .where("conversation_id", "==", conversation_id)
            .order_by("sequence_no", direction=Query.ASCENDING)
            .stream()
        )
        result: list[LedgerEntry] = []
        for snap in snaps:
            data = snap.to_dict()
            if data is None:
                continue
            try:
                result.append(_dict_to_entry(data))
            except Exception:
                _log.warning("Skipping malformed ledger entry %s", snap.id)
        return result

    return await asyncio.to_thread(_query)
