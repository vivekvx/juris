from datetime import datetime, timezone
from typing import Any, cast

from google.cloud.firestore import DocumentSnapshot

from app.core.firebase import get_firestore_client
from app.models.user import User, UserDocument

_COLLECTION = "users"


def _utc_now() -> datetime:
    return datetime.now(tz=timezone.utc)


def get_user(uid: str) -> UserDocument | None:
    doc = cast(DocumentSnapshot, get_firestore_client().collection(_COLLECTION).document(uid).get())
    if not doc.exists:
        return None
    data = doc.to_dict()
    if data is None:
        return None
    return UserDocument.model_validate(data)


def create_user_if_missing(user: User) -> UserDocument:
    ref = get_firestore_client().collection(_COLLECTION).document(user.uid)
    doc = cast(DocumentSnapshot, ref.get())
    if doc.exists:
        data = doc.to_dict()
        if data is not None:
            return UserDocument.model_validate(data)
    now = _utc_now()
    user_doc = UserDocument(
        uid=user.uid,
        email=user.email,
        display_name=user.display_name,
        photo_url=user.photo_url,
        created_at=now,
        updated_at=now,
    )
    ref.set(user_doc.model_dump())
    return user_doc


def upsert_user(user: User) -> UserDocument:
    ref = get_firestore_client().collection(_COLLECTION).document(user.uid)
    doc = cast(DocumentSnapshot, ref.get())
    now = _utc_now()
    if doc.exists:
        data = doc.to_dict()
        if data is not None:
            existing = UserDocument.model_validate(data)
            updates: dict[str, Any] = {
                "display_name": user.display_name,
                "photo_url": user.photo_url,
                "updated_at": now,
            }
            ref.update(updates)
            return UserDocument(
                uid=existing.uid,
                email=existing.email,
                display_name=user.display_name,
                photo_url=user.photo_url,
                preferred_language=existing.preferred_language,
                created_at=existing.created_at,
                updated_at=now,
            )
    user_doc = UserDocument(
        uid=user.uid,
        email=user.email,
        display_name=user.display_name,
        photo_url=user.photo_url,
        created_at=now,
        updated_at=now,
    )
    ref.set(user_doc.model_dump())
    return user_doc
