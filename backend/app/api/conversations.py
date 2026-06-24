"""Conversation API routes (CRUD only — streaming chat is in chat.py).

Routes orchestrate services only — no Firestore, no Firebase here.
Ownership checks return 404 so callers cannot enumerate other users' resources.
"""
from __future__ import annotations

import uuid
from datetime import datetime, timezone

from fastapi import APIRouter, Depends, status
from pydantic import BaseModel

from app.core.auth import get_current_user
from app.models.conversation import Conversation
from app.models.user import User
from app.services.conversations import (
    create_conversation,
    delete_conversation,
    get_conversation,
    list_conversations,
    list_messages,
    patch_conversation,
)
from app.services.documents import get_document

router = APIRouter(prefix="/api/conversations", tags=["conversations"])


# ---------------------------------------------------------------------------
# Request bodies
# ---------------------------------------------------------------------------

class CreateConversationRequest(BaseModel):
    title: str


class PatchConversationRequest(BaseModel):
    document_ids: list[str] | None = None  # None resets to "all docs" mode
    title: str | None = None


# ---------------------------------------------------------------------------
# Response shapes (owner_uid / title_generated never returned)
# ---------------------------------------------------------------------------

class ConversationResponse(BaseModel):
    id: str
    title: str
    created_at: str
    updated_at: str
    last_message_at: str | None
    document_ids: list[str] | None = None


class MessageResponse(BaseModel):
    id: str
    role: str
    content: str
    created_at: str
    citations: list[dict[str, object]] | None = None


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _conv_response(conv: Conversation) -> ConversationResponse:
    data = conv.model_dump(mode="json", exclude={"owner_uid", "title_generated"})
    return ConversationResponse(**data)


def _msg_response(msg_data: dict[str, object]) -> MessageResponse:
    return MessageResponse(
        id=str(msg_data["id"]),
        role=str(msg_data["role"]),
        content=str(msg_data["content"]),
        created_at=str(msg_data["created_at"]),
        citations=msg_data.get("citations"),  # type: ignore[arg-type]
    )


# ---------------------------------------------------------------------------
# Routes
# ---------------------------------------------------------------------------

@router.post("/", response_model=ConversationResponse, status_code=status.HTTP_201_CREATED)
def create_conversation_route(
    body: CreateConversationRequest,
    current_user: User = Depends(get_current_user),
) -> ConversationResponse:
    now = datetime.now(tz=timezone.utc)
    conv = create_conversation(
        Conversation(
            id=str(uuid.uuid4()),
            owner_uid=current_user.uid,
            title=body.title,
            created_at=now,
            updated_at=now,
        )
    )
    return _conv_response(conv)


@router.get("/", response_model=list[ConversationResponse])
def list_conversations_route(
    limit: int = 20,
    current_user: User = Depends(get_current_user),
) -> list[ConversationResponse]:
    limit = min(max(1, limit), 100)
    return [_conv_response(c) for c in list_conversations(current_user.uid, limit=limit)]


@router.get("/{conv_id}", response_model=ConversationResponse)
def get_conversation_route(
    conv_id: str,
    current_user: User = Depends(get_current_user),
) -> ConversationResponse:
    return _conv_response(get_conversation(conv_id, current_user.uid))


@router.patch("/{conv_id}", response_model=ConversationResponse)
def patch_conversation_route(
    conv_id: str,
    body: PatchConversationRequest,
    current_user: User = Depends(get_current_user),
) -> ConversationResponse:
    updates: dict[str, object] = {}

    if body.document_ids is not None:
        # Validate each doc_id belongs to this user (raises 404 otherwise)
        for doc_id in body.document_ids:
            get_document(doc_id, current_user.uid)
        updates["document_ids"] = body.document_ids
    else:
        updates["document_ids"] = None  # reset to "all docs" mode

    if body.title is not None:
        updates["title"] = body.title

    conv = patch_conversation(conv_id, current_user.uid, updates)
    return _conv_response(conv)


@router.delete("/{conv_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_conversation_route(
    conv_id: str,
    current_user: User = Depends(get_current_user),
) -> None:
    delete_conversation(conv_id, current_user.uid)


@router.get("/{conv_id}/messages", response_model=list[MessageResponse])
def list_messages_route(
    conv_id: str,
    limit: int = 50,
    current_user: User = Depends(get_current_user),
) -> list[MessageResponse]:
    limit = min(max(1, limit), 200)
    return [_msg_response(m.model_dump(mode="json")) for m in list_messages(conv_id, current_user.uid, limit=limit)]
