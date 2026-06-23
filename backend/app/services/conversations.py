"""Conversation service layer — Firestore operations only.

No HTTP concerns, no request parsing. Ownership checks return 404 (not 403)
so non-owned resources are indistinguishable from missing ones.
All timestamps stored as ISO-8601 UTC strings, consistent with documents service.
"""
from __future__ import annotations

from datetime import datetime, timezone
from typing import cast

from fastapi import HTTPException
from google.cloud.firestore import DocumentSnapshot

from app.core.firebase import get_firestore_client
from app.models.conversation import Conversation, Message

_CONVERSATIONS = "conversations"
_MESSAGES = "messages"
_FIRESTORE_BATCH_LIMIT = 500


def _utc_now() -> datetime:
    return datetime.now(tz=timezone.utc)


def _iso(dt: datetime) -> str:
    return dt.isoformat().replace("+00:00", "Z")


def _snap_to_conversation(snap: DocumentSnapshot) -> Conversation:
    data = snap.to_dict()
    if data is None:
        raise HTTPException(status_code=404, detail="Conversation not found.")
    return Conversation.model_validate(data)


def _snap_to_message(snap: DocumentSnapshot) -> Message:
    data = snap.to_dict()
    if data is None:
        raise HTTPException(status_code=404, detail="Message not found.")
    return Message.model_validate(data)


def _get_and_authorize(conv_id: str, owner_uid: str) -> tuple[DocumentSnapshot, Conversation]:
    """Fetch a conversation and verify ownership. Returns (snap, conv).

    Raises 404 for missing or wrong-owner resources so callers cannot enumerate
    other users' conversation IDs.
    """
    ref = get_firestore_client().collection(_CONVERSATIONS).document(conv_id)
    snap = cast(DocumentSnapshot, ref.get())
    if not snap.exists:
        raise HTTPException(status_code=404, detail="Conversation not found.")
    conv = _snap_to_conversation(snap)
    if conv.owner_uid != owner_uid:
        raise HTTPException(status_code=404, detail="Conversation not found.")
    return snap, conv


def create_conversation(conversation: Conversation) -> Conversation:
    ref = get_firestore_client().collection(_CONVERSATIONS).document(conversation.id)
    ref.set(conversation.model_dump())
    return conversation


def get_conversation(conv_id: str, owner_uid: str) -> Conversation:
    _, conv = _get_and_authorize(conv_id, owner_uid)
    return conv


def list_conversations(owner_uid: str, limit: int = 20) -> list[Conversation]:
    snaps = (
        get_firestore_client()
        .collection(_CONVERSATIONS)
        .where("owner_uid", "==", owner_uid)
        .stream()
    )
    result: list[Conversation] = []
    for snap in snaps:
        data = snap.to_dict()
        if data is not None:
            result.append(Conversation.model_validate(data))

    # Sort: last_message_at DESC NULLS LAST, then created_at DESC.
    # Nones sort last because (True > False) pushes them after non-Nones.
    result.sort(
        key=lambda c: (
            c.last_message_at is None,
            -(c.last_message_at.timestamp() if c.last_message_at else 0),
            -c.created_at.timestamp(),
        )
    )
    return result[:limit]


def delete_conversation(conv_id: str, owner_uid: str) -> None:
    db = get_firestore_client()
    conv_ref = db.collection(_CONVERSATIONS).document(conv_id)
    _get_and_authorize(conv_id, owner_uid)

    # Batch-delete messages subcollection before the parent document.
    messages_ref = conv_ref.collection(_MESSAGES)
    while True:
        docs = list(messages_ref.limit(_FIRESTORE_BATCH_LIMIT).stream())
        if not docs:
            break
        batch = db.batch()
        for doc in docs:
            batch.delete(doc.reference)
        batch.commit()

    conv_ref.delete()


def create_message(conv_id: str, owner_uid: str, content: str) -> Message:
    db = get_firestore_client()
    conv_ref = db.collection(_CONVERSATIONS).document(conv_id)
    _get_and_authorize(conv_id, owner_uid)

    now = _utc_now()
    msg_ref = conv_ref.collection(_MESSAGES).document()
    message = Message(id=msg_ref.id, role="user", content=content, created_at=now)
    msg_ref.set(message.model_dump())

    # Denormalize last_message_at onto the conversation for list ordering.
    conv_ref.update({"last_message_at": _iso(now), "updated_at": _iso(now)})

    return message


def list_messages(conv_id: str, owner_uid: str, limit: int = 50) -> list[Message]:
    db = get_firestore_client()
    conv_ref = db.collection(_CONVERSATIONS).document(conv_id)
    _get_and_authorize(conv_id, owner_uid)

    snaps = conv_ref.collection(_MESSAGES).order_by("created_at").limit(limit).stream()
    return [_snap_to_message(s) for s in snaps]
