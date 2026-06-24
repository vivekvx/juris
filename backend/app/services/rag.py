"""RAG pipeline: retrieve chunks → build Gemini context."""
from __future__ import annotations

import asyncio
import logging

from app.config.settings import get_settings
from app.models.chunk import ChunkCitation
from app.repositories.chunk_repo import build_citation, cosine_top_k, load_chunks_for_user
from app.services.documents import get_document

_log = logging.getLogger(__name__)


async def retrieve(
    uid: str,
    query_vec: list[float],
    doc_ids: list[str] | None,
) -> list[ChunkCitation]:
    """Load user chunks and return top-k citations for a pre-embedded query vector."""
    settings = get_settings()
    chunks = await load_chunks_for_user(uid)
    top = cosine_top_k(
        query_vec,
        chunks,
        top_k=settings.retrieval_top_k,
        doc_ids=doc_ids,
        score_threshold=settings.citation_score_threshold,
    )
    if not top:
        return []

    filenames: dict[str, str] = {}
    for doc_id in {c.doc_id for c, _ in top}:
        try:
            doc = await asyncio.to_thread(get_document, doc_id, uid)
            filenames[doc_id] = doc.original_filename
        except Exception:
            filenames[doc_id] = doc_id

    return [build_citation(c, filenames.get(c.doc_id, c.doc_id), score) for c, score in top]


def build_context(citations: list[ChunkCitation]) -> str:
    """Format citations as a numbered source block for the system prompt."""
    if not citations:
        return ""
    lines = ["[DOCUMENTS]"]
    for i, c in enumerate(citations, 1):
        loc = f" (page {c.page_number})" if c.page_number else ""
        lines.append(f"[{i}] {c.original_filename}{loc}")
        lines.append(c.content)
        lines.append("")
    lines.append("[/DOCUMENTS]")
    return "\n".join(lines)
