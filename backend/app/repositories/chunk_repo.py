"""Firestore chunk repository — write, delete, and load chunks.

Collection group query (`load_chunks_for_user`) requires a Firestore
composite index on `chunks` collection group, field `owner_uid ASC`.
Deploy firestore.indexes.json before M4 retrieval is used.
"""
from __future__ import annotations

import asyncio
import logging

import numpy as np

from app.core.firebase import get_firestore_client
from app.models.chunk import Chunk, ChunkCitation

_log = logging.getLogger(__name__)
_FIRESTORE_BATCH_LIMIT = 500


def _chunk_to_dict(chunk: Chunk) -> dict[str, object]:
    return {
        "id":              chunk.id,
        "doc_id":          chunk.doc_id,
        "owner_uid":       chunk.owner_uid,
        "content":         chunk.content,
        "embedding":       chunk.embedding,
        "chunk_index":     chunk.chunk_index,
        "page_number":     chunk.page_number,
        "token_count":     chunk.token_count,
        "chunk_version":   chunk.chunk_version,
        "embedding_model": chunk.embedding_model,
        "created_at":      chunk.created_at.isoformat().replace("+00:00", "Z"),
    }


async def write_chunks(doc_id: str, chunks: list[Chunk]) -> None:
    """Batch-write chunks to documents/{doc_id}/chunks/. Handles >500 chunks via multi-batch."""
    db = get_firestore_client()
    chunks_ref = db.collection("documents").document(doc_id).collection("chunks")

    for batch_start in range(0, len(chunks), _FIRESTORE_BATCH_LIMIT):
        batch = db.batch()
        for chunk in chunks[batch_start : batch_start + _FIRESTORE_BATCH_LIMIT]:
            ref = chunks_ref.document(chunk.id)
            batch.set(ref, _chunk_to_dict(chunk))
        await asyncio.to_thread(batch.commit)

    _log.info("Wrote %d chunks for doc %s", len(chunks), doc_id)


async def delete_chunks(doc_id: str) -> None:
    """Delete all chunks for a document. Safe to call when subcollection is already empty."""
    db = get_firestore_client()
    chunks_ref = db.collection("documents").document(doc_id).collection("chunks")

    while True:
        snaps = await asyncio.to_thread(
            lambda: list(chunks_ref.limit(_FIRESTORE_BATCH_LIMIT).stream())
        )
        if not snaps:
            break
        batch = db.batch()
        for snap in snaps:
            batch.delete(snap.reference)
        await asyncio.to_thread(batch.commit)

    _log.info("Deleted chunks for doc %s", doc_id)


async def load_chunks_for_user(uid: str) -> list[Chunk]:
    """Load all indexed chunks for a user via collection group query.

    Requires Firestore composite index: collectionGroup=chunks, owner_uid ASC.
    See firestore.indexes.json at project root.
    """
    db = get_firestore_client()
    snaps = await asyncio.to_thread(
        lambda: list(
            db.collection_group("chunks").where("owner_uid", "==", uid).stream()
        )
    )
    chunks: list[Chunk] = []
    for snap in snaps:
        data = snap.to_dict()
        if data is None:
            continue
        try:
            chunks.append(Chunk.model_validate(data))
        except Exception:
            _log.warning("Skipping malformed chunk %s", snap.id)
    return chunks


def cosine_top_k(
    query: list[float],
    chunks: list[Chunk],
    top_k: int,
    doc_ids: list[str] | None,
    score_threshold: float,
) -> list[tuple[Chunk, float]]:
    """In-Python cosine similarity over chunk list. Returns top_k pairs above threshold."""
    if not chunks:
        return []

    filtered = [c for c in chunks if doc_ids is None or c.doc_id in doc_ids]
    if not filtered:
        return []

    matrix = np.array([c.embedding for c in filtered], dtype=np.float32)
    q = np.array(query, dtype=np.float32)
    q /= np.linalg.norm(q) + 1e-10
    norms = np.linalg.norm(matrix, axis=1, keepdims=True) + 1e-10
    scores: np.ndarray = (matrix / norms) @ q

    top_indices = np.argsort(scores)[::-1][:top_k]
    return [
        (filtered[int(i)], float(scores[i]))
        for i in top_indices
        if float(scores[i]) >= score_threshold
    ]


def build_citation(chunk: Chunk, original_filename: str, score: float) -> ChunkCitation:
    return ChunkCitation(
        doc_id=chunk.doc_id,
        original_filename=original_filename,
        chunk_index=chunk.chunk_index,
        page_number=chunk.page_number,
        content=chunk.content,
        score=round(score, 4),
    )
