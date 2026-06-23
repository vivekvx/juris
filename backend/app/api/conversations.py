"""Conversation API routes.

Routes orchestrate services only — no Firestore, no Firebase here.
All role assignment is server-side ("user" hardcoded in M2; M3 adds AI responses).
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
    create_message,
    delete_conversation,
    get_conversation,
    list_conversations,
    list_messages,
)

router = APIRouter(prefix="/api/conversations", tags=["conversations"])


# ---------------------------------------------------------------------------
# Request bodies
# ---------------------------------------------------------------------------

class CreateConversationRequest(BaseModel):
    title: str


class CreateMessageRequest(BaseModel):
    content: str


# ---------------------------------------------------------------------------
# Response shapes (owner_uid never returned)
# ---------------------------------------------------------------------------

class ConversationResponse(BaseModel):
    id: str
    title: str
    created_at: str
    updated_at: str
    last_message_at: str | None


class MessageResponse(BaseModel):
    id: str
    role: str
    content: str
    created_at: str


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _conv_response(conv: Conversation) -> ConversationResponse:
    data = conv.model_dump(mode="json", exclude={"owner_uid"})
    return ConversationResponse(**data)


def _msg_response(msg_data: dict[str, object]) -> MessageResponse:
    return MessageResponse(
        id=str(msg_data["id"]),
        role=str(msg_data["role"]),
        content=str(msg_data["content"]),
        created_at=str(msg_data["created_at"]),
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


@router.delete("/{conv_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_conversation_route(
    conv_id: str,
    current_user: User = Depends(get_current_user),
) -> None:
    delete_conversation(conv_id, current_user.uid)


@router.post(
    "/{conv_id}/messages",
    response_model=MessageResponse,
    status_code=status.HTTP_201_CREATED,
)
def create_message_route(
    conv_id: str,
    body: CreateMessageRequest,
    current_user: User = Depends(get_current_user),
) -> MessageResponse:
    msg = create_message(conv_id, current_user.uid, body.content)
    return _msg_response(msg.model_dump(mode="json"))


@router.get("/{conv_id}/messages", response_model=list[MessageResponse])
def list_messages_route(
    conv_id: str,
    limit: int = 50,
    current_user: User = Depends(get_current_user),
) -> list[MessageResponse]:
    limit = min(max(1, limit), 200)
    return [_msg_response(m.model_dump(mode="json")) for m in list_messages(conv_id, current_user.uid, limit=limit)]
