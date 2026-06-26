"""SSE streaming endpoint for RAG-powered chat.

Takes over POST /{conv_id}/messages from conversations.py.
Protocol: event: token | citations | policy | done | error
"""
from __future__ import annotations

import asyncio
import json
import logging
from collections.abc import AsyncGenerator

from fastapi import APIRouter, Depends
from fastapi.responses import StreamingResponse
from pydantic import BaseModel

from app.core.auth import get_current_user
from app.models.chunk import ChunkCitation
from app.models.conversation import Conversation
from app.models.ledger import PolicyEvaluation, PolicyRecord
from app.models.policy import (
    OrgRole,
    PolicyDecision,
    PolicyEffect,
    PolicyEvaluationContext,
    PolicyTrigger,
)
from app.models.user import User
from app.services.conversations import (
    create_assistant_message,
    create_message,
    get_conversation,
    list_messages,
    patch_conversation,
)
from app.services.embedding import embed_query
from app.services.ledger import log_decision
from app.services.llm import generate_title, stream_response
from app.services.policy import default_snapshot
from app.services.policy import evaluate as policy_evaluate
from app.services.rag import build_context, retrieve

# Strong references prevent GC of fire-and-forget title tasks.
_background_tasks: set[asyncio.Task[None]] = set()

router = APIRouter(prefix="/api/conversations", tags=["chat"])
_log = logging.getLogger(__name__)

# Fallback policy_id recorded in the ledger when the engine returns default-allow.
_DEFAULT_POLICY_ENTRY_ID = "default"


class SendMessageRequest(BaseModel):
    content: str
    document_ids: list[str] | None = None


def _sse(event: str, data: dict[str, object]) -> str:
    return f"event: {event}\ndata: {json.dumps(data)}\n\n"


def _policy_ctx(
    uid: str,
    trigger: PolicyTrigger,
    *,
    query: str | None = None,
) -> PolicyEvaluationContext:
    # ponytail: personal org only (actor_role=MEMBER); org membership comes with M6.3
    return PolicyEvaluationContext(
        org_id=uid,
        actor_uid=uid,
        actor_role=OrgRole.MEMBER,
        trigger=trigger,
        query=query,
        document_tags=[],
        detected_topics=[],
        pii_detected=False,
    )


def _decision_to_evaluation(decision: PolicyDecision) -> PolicyEvaluation:
    return PolicyEvaluation(
        trigger=decision.trigger,
        effect=decision.effect,
        policy_id=decision.policy_id or _DEFAULT_POLICY_ENTRY_ID,
    )


async def _save_title(conv_id: str, uid: str, user_msg: str, asst_msg: str) -> None:
    try:
        title = await generate_title(user_msg, asst_msg)
        if title:
            await asyncio.to_thread(
                patch_conversation,
                conv_id,
                uid,
                {"title": title, "title_generated": True},
            )
    except Exception as exc:
        _log.warning("Title generation failed for conv %s: %s", conv_id, exc)


async def _stream(
    conv: Conversation,
    content: str,
    request_doc_ids: list[str] | None,
    uid: str,
) -> AsyncGenerator[str, None]:
    history = await asyncio.to_thread(list_messages, conv.id, uid, 10, True)

    # Obtain policy snapshot once per request (personal org → empty → always allow).
    snapshot = default_snapshot(uid)

    # [on-query] evaluate before embedding — DENY short-circuits before any state change.
    query_decision = policy_evaluate(
        snapshot, _policy_ctx(uid, PolicyTrigger.ON_QUERY, query=content)
    )
    if query_decision.effect == PolicyEffect.DENY:
        yield _sse("policy", {
            "effect": query_decision.effect.value,
            "message": query_decision.message,
            "trigger": PolicyTrigger.ON_QUERY.value,
        })
        yield _sse("error", {"detail": query_decision.message})
        return

    # Embed FIRST — failure means no user message is written (spec §10)
    try:
        query_vec = await embed_query(content)
    except Exception as exc:
        _log.error("Embed failed for conv %s: %s", conv.id, exc)
        yield _sse("error", {"detail": "Failed to process your message. Please try again."})
        return

    # Write user message only after embed succeeds
    await asyncio.to_thread(create_message, conv.id, uid, content)

    doc_ids = request_doc_ids if request_doc_ids is not None else conv.document_ids

    citations: list[ChunkCitation] = []
    try:
        citations = await retrieve(uid, query_vec, doc_ids)
    except Exception as exc:
        _log.warning("Retrieval failed for conv %s: %s", conv.id, exc)

    context = build_context(citations)
    citation_dicts: list[dict[str, object]] = [c.model_dump() for c in citations]

    accumulated = ""
    try:
        async for token in stream_response(history, context, content):
            accumulated += token
            yield _sse("token", {"text": token})
    except (asyncio.CancelledError, GeneratorExit):
        # Client disconnected — do not write orphan message
        raise
    except Exception as exc:
        _log.error("LLM stream error for conv %s: %s", conv.id, exc)
        final = accumulated + ("\n\n[Response interrupted]" if accumulated else "[Response failed]")
        await asyncio.to_thread(create_assistant_message, conv.id, uid, final, citation_dicts)
        yield _sse("error", {"detail": "Response generation failed. Partial response saved."})
        return

    # [on-release] evaluate before persisting — apply effect before saving to conversation.
    release_decision = policy_evaluate(
        snapshot, _policy_ctx(uid, PolicyTrigger.ON_RELEASE, query=content)
    )

    if release_decision.effect == PolicyEffect.DENY:
        yield _sse("policy", {
            "effect": release_decision.effect.value,
            "message": release_decision.message,
            "trigger": PolicyTrigger.ON_RELEASE.value,
        })
        yield _sse("error", {"detail": release_decision.message})
        return

    if release_decision.effect == PolicyEffect.REQUIRE_APPROVAL:
        yield _sse("policy", {
            "effect": release_decision.effect.value,
            "message": release_decision.message,
            "trigger": PolicyTrigger.ON_RELEASE.value,
        })
        return  # held — no assistant message persisted, no done event

    if release_decision.effect == PolicyEffect.REDACT:
        accumulated = f"[Redacted: {release_decision.message}]"

    asst_msg = await asyncio.to_thread(
        create_assistant_message, conv.id, uid, accumulated, citation_dicts
    )

    yield _sse("citations", {"citations": citation_dicts, "sources_used": bool(citations)})

    # Emit policy SSE for non-silent effects (warn, redact, require_ledger).
    if release_decision.effect != PolicyEffect.ALLOW:
        yield _sse("policy", {
            "effect": release_decision.effect.value,
            "message": release_decision.message,
            "trigger": PolicyTrigger.ON_RELEASE.value,
        })

    # Capture both seam evaluations in the ledger policy record.
    policy_record = PolicyRecord(
        snapshot_id=snapshot.id,
        evaluations=[
            _decision_to_evaluation(query_decision),
            _decision_to_evaluation(release_decision),
        ],
    )

    # Append ledger entry before done — degrade gracefully on failure.
    ledger_ok = False
    try:
        await log_decision(
            org_id=uid,  # personal org (uid == org_id) until M6.3 adds Organization
            conv_id=conv.id,
            actor_uid=uid,
            message_id=asst_msg.id,
            query=content,
            document_ids=doc_ids or [],
            citations=citations,
            accumulated_answer=accumulated,
            sources_used=bool(citations),
            policy_record=policy_record,
        )
        ledger_ok = True
    except Exception as exc:
        _log.error("Ledger write failed for conv %s: %s", conv.id, exc)

    # require_ledger: withhold done if the mandatory ledger write failed.
    if not ledger_ok and release_decision.effect == PolicyEffect.REQUIRE_LEDGER:
        yield _sse("error", {"detail": "Response withheld: mandatory ledger write failed."})
        return

    yield _sse("done", {"message_id": asst_msg.id})

    if not conv.title_generated:
        task: asyncio.Task[None] = asyncio.create_task(
            _save_title(conv.id, uid, content, accumulated)
        )
        _background_tasks.add(task)
        task.add_done_callback(_background_tasks.discard)


@router.post("/{conv_id}/messages")
async def send_message(
    conv_id: str,
    body: SendMessageRequest,
    current_user: User = Depends(get_current_user),
) -> StreamingResponse:
    conv = await asyncio.to_thread(get_conversation, conv_id, current_user.uid)
    return StreamingResponse(
        _stream(conv, body.content, body.document_ids, current_user.uid),
        media_type="text/event-stream",
        headers={"Cache-Control": "no-cache", "X-Accel-Buffering": "no"},
    )
