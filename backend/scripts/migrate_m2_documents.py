"""M2 → M3 migration: process existing READY documents that lack indexed_at.

M2 documents are status=READY with indexed_at=None (no chunks, not retrievable).
This script finds them and runs the M3 processing pipeline for each.

Usage (from backend/ directory with .env set):
    python -m scripts.migrate_m2_documents [--dry-run] [--limit N]

Requirements:
    - FIREBASE_CREDENTIALS, FIREBASE_PROJECT_ID, FIREBASE_STORAGE_BUCKET,
      GOOGLE_API_KEY must be set in .env or environment.
    - Run from the backend/ directory so app imports resolve.
"""
from __future__ import annotations

import argparse
import asyncio
import logging
import sys

logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(message)s")
_log = logging.getLogger(__name__)


def _find_unindexed_ready_docs() -> list[dict[str, str]]:
    """Return [{id, owner_uid}] for READY documents with no indexed_at."""
    from app.core.firebase import get_firestore_client

    db = get_firestore_client()
    snaps = db.collection("documents").where("status", "==", "READY").stream()
    result = []
    for snap in snaps:
        data = snap.to_dict()
        if data and data.get("indexed_at") is None:
            result.append({"id": snap.id, "owner_uid": str(data["owner_uid"])})
    return result


async def _process_one(doc_id: str, owner_uid: str) -> None:
    """Force READY → PROCESSING (bypassing the state machine guard) then run the pipeline."""
    from datetime import datetime, timezone

    from app.core.firebase import get_firestore_client
    from app.models.document import DocumentStatus
    from app.services.processing import process_document

    now = datetime.now(tz=timezone.utc)
    get_firestore_client().collection("documents").document(doc_id).update({
        "status": DocumentStatus.PROCESSING.value,
        "processing_started_at": now,
        "updated_at": now,
    })
    await process_document(doc_id, owner_uid)


async def main(dry_run: bool, limit: int | None) -> None:
    docs = _find_unindexed_ready_docs()
    _log.info("Found %d unindexed READY documents", len(docs))

    if limit is not None:
        docs = docs[:limit]
        _log.info("Limiting to first %d", limit)

    if dry_run:
        for d in docs:
            _log.info("[dry-run] Would process doc %s (owner: %s)", d["id"], d["owner_uid"])
        return

    ok = 0
    for i, d in enumerate(docs, 1):
        _log.info("Processing %d/%d: doc %s", i, len(docs), d["id"])
        try:
            await _process_one(d["id"], d["owner_uid"])
            _log.info("  OK doc %s", d["id"])
            ok += 1
        except Exception as exc:
            _log.error("  FAIL doc %s: %s", d["id"], exc)

    _log.info("Done: %d/%d succeeded", ok, len(docs))


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Migrate M2 READY docs to M3 indexed state")
    parser.add_argument("--dry-run", action="store_true", help="List without processing")
    parser.add_argument("--limit", type=int, default=None, help="Process at most N docs")
    args = parser.parse_args()
    asyncio.run(main(dry_run=args.dry_run, limit=args.limit))
