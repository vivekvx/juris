"""SSE streaming endpoint for RAG-powered chat.

Takes over POST /{conv_id}/messages from conversations.py.
Protocol: event: token | citations | done | error
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
from app.models.user import User
from app.services.conversations import (
    create_assistant_message,
    create_message,
    get_conversation,
    list_messages,
    patch_conversation,
)
from app.services.llm import generate_title, stream_response
from app.services.rag import build_context, retrieve

router = APIRouter(prefix="/api/conversations", tags=["chat"])
_log = logging.getLogger(__name__)


class SendMessageRequest(BaseModel):
    content: str
    document_ids: list[str] | None = None


def _sse(event: str, data: dict[str, object]) -> str:
    return f"event: {event}\ndata: {json.dumps(data)}\n\n"


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

    await asyncio.to_thread(create_message, conv.id, uid, content)

    # request_doc_ids=None means use the conversation's scoping (which may also be None = all docs)
    doc_ids = request_doc_ids if request_doc_ids is not None else conv.document_ids

    citations: list[ChunkCitation] = []
    try:
        citations = await retrieve(uid, content, doc_ids)
    except Exception as exc:
        _log.warning("Retrieval failed for conv %s: %s", conv.id, exc)

    context = build_context(citations)
    citation_dicts: list[dict[str, object]] = [c.model_dump() for c in citations]

    accumulated = ""
    try:
        async for token in stream_response(history, context, content):
            accumulated += token
            yield _sse("token", {"text": token})
    except Exception as exc:
        _log.error("LLM stream error for conv %s: %s", conv.id, exc)
        final = accumulated + ("\n\n[Response interrupted]" if accumulated else "[Response failed]")
        await asyncio.to_thread(create_assistant_message, conv.id, uid, final, citation_dicts)
        yield _sse("error", {"detail": "Response generation failed. Partial response saved."})
        return

    asst_msg = await asyncio.to_thread(
        create_assistant_message, conv.id, uid, accumulated, citation_dicts
    )

    yield _sse("citations", {"citations": citation_dicts, "sources_used": bool(citations)})
    yield _sse("done", {"message_id": asst_msg.id})

    if not conv.title_generated:
        asyncio.create_task(_save_title(conv.id, uid, content, accumulated))


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
