"""AI Decision Ledger service — assembles and persists DecisionEvents.

Thin assembly layer between the chat pipeline and the repository.
Determines sequence_no and prev_hash from the org's latest entry,
computes the entry_hash, and delegates persistence to ledger_repo.
No business logic; all I/O goes through the repository.
"""
from __future__ import annotations

import hashlib
import logging
import uuid
from datetime import datetime, timezone

from app.config.settings import get_settings
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
from app.repositories.ledger_repo import append_entry, compute_entry_hash, get_latest_entry
from app.services.llm import (
    LLM_MAX_OUTPUT_TOKENS,
    LLM_MODEL_NAME,
    LLM_TEMPERATURE,
    PROMPT_TEMPLATE_VERSION,
)

_log = logging.getLogger(__name__)

_GENESIS_HASH = "sha256:genesis"
_DEFAULT_POLICY_ID = "default-allow"
_DEFAULT_SNAPSHOT_ID = "default"


def _sha256_hex(text: str) -> str:
    return "sha256:" + hashlib.sha256(text.encode()).hexdigest()


def _build_retrieval(
    citations: list[ChunkCitation],
    top_k: int,
    score_threshold: float,
) -> RetrievalRecord:
    return RetrievalRecord(
        params=RetrievalParams(top_k=top_k, score_threshold=score_threshold),
        citations=[
            CachedCitation(
                doc_id=c.doc_id,
                chunk_index=c.chunk_index,
                page_number=c.page_number,
                score=c.score,
                original_filename=c.original_filename,
            )
            for c in citations
        ],
    )


def _default_policy() -> PolicyRecord:
    return PolicyRecord(
        snapshot_id=_DEFAULT_SNAPSHOT_ID,
        evaluations=[
            PolicyEvaluation(
                trigger=PolicyTrigger.ON_RELEASE,
                effect=PolicyEffect.ALLOW,
                policy_id=_DEFAULT_POLICY_ID,
            )
        ],
    )


async def log_decision(
    org_id: str,
    conv_id: str,
    actor_uid: str,
    message_id: str,
    query: str,
    document_ids: list[str],
    citations: list[ChunkCitation],
    accumulated_answer: str,
    sources_used: bool,
    policy_record: PolicyRecord | None = None,
) -> None:
    """Build and append one DecisionEvent for a completed AI response.

    Reads the latest org entry to establish sequence_no and prev_hash (genesis
    values when the ledger is empty). Computes entry_hash before appending.
    Callers must catch and handle exceptions for graceful degradation.
    """
    settings = get_settings()

    latest = await get_latest_entry(org_id)
    prev_hash = _GENESIS_HASH if latest is None else latest.entry_hash
    sequence_no = 1 if latest is None else latest.sequence_no + 1

    top_score = max((c.score for c in citations), default=0.0)

    draft = DecisionEvent(
        id=str(uuid.uuid4()),
        org_id=org_id,
        kind=DecisionKind.DECISION,
        sequence_no=sequence_no,
        actor_uid=actor_uid,
        conversation_id=conv_id,
        message_id=message_id,
        query=query,
        document_ids=document_ids,
        retrieval=_build_retrieval(
            citations, settings.retrieval_top_k, settings.citation_score_threshold
        ),
        memory_used=[],
        model=ModelParams(
            name=LLM_MODEL_NAME,
            temperature=LLM_TEMPERATURE,
            max_output_tokens=LLM_MAX_OUTPUT_TOKENS,
            prompt_template_version=PROMPT_TEMPLATE_VERSION,
        ),
        policy=policy_record if policy_record is not None else _default_policy(),
        output=OutputRecord(
            answer_hash=_sha256_hex(accumulated_answer),
            answer_ref=message_id,
            sources_used=sources_used,
            grounding=GroundingStatus(
                citations_above_threshold=len(citations),
                top_score=top_score,
                disclaimer_emitted=not sources_used,
            ),
        ),
        prev_hash=prev_hash,
        entry_hash="sha256:placeholder",
        created_at=datetime.now(tz=timezone.utc),
    )
    entry = draft.model_copy(update={"entry_hash": compute_entry_hash(draft)})
    await append_entry(org_id, entry)
    _log.info(
        "Decision logged: org=%s conv=%s seq=%s msg=%s",
        org_id, conv_id, sequence_no, message_id,
    )
