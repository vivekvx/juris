from fastapi import APIRouter, Depends, status
from pydantic import BaseModel

from app.core.auth import get_current_user
from app.models.user import User
from app.services.users import create_user_if_missing

router = APIRouter(prefix="/api/users", tags=["users"])


class UserProfileResponse(BaseModel):
    uid: str
    email: str | None
    display_name: str | None
    photo_url: str | None
    preferred_language: str


@router.post("/me", response_model=UserProfileResponse, status_code=status.HTTP_200_OK)
def post_me(current_user: User = Depends(get_current_user)) -> UserProfileResponse:
    """Ensure the authenticated user's Firestore profile exists and return it.

    Creates the profile on first login. Returns the existing profile on
    subsequent calls without overwriting created_at or preferred_language.
    """
    profile = create_user_if_missing(current_user)
    return UserProfileResponse(
        uid=profile.uid,
        email=profile.email,
        display_name=profile.display_name,
        photo_url=profile.photo_url,
        preferred_language=profile.preferred_language,
    )
