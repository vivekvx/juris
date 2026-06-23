from datetime import datetime

from pydantic import BaseModel


class User(BaseModel):
    uid: str
    email: str | None
    display_name: str | None
    photo_url: str | None


class UserDocument(BaseModel):
    uid: str
    email: str | None
    display_name: str | None
    photo_url: str | None
    preferred_language: str = "en"
    created_at: datetime
    updated_at: datetime
