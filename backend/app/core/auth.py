from typing import Any

import firebase_admin.auth  # type: ignore[import-untyped]
from fastapi import Depends, HTTPException, status
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer

from app.core.firebase import get_firebase_app
from app.models.user import User

# auto_error=False so we can return 401 (not 403) for missing/malformed headers
_bearer = HTTPBearer(auto_error=False)


def verify_firebase_token(
    credentials: HTTPAuthorizationCredentials | None = Depends(_bearer),
) -> dict[str, Any]:
    if credentials is None:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Authorization header is required.",
        )
    try:
        decoded: dict[str, Any] = firebase_admin.auth.verify_id_token(
            credentials.credentials,
            app=get_firebase_app(),
        )
        return decoded
    except firebase_admin.auth.ExpiredIdTokenError:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Token has expired.",
        )
    except firebase_admin.auth.RevokedIdTokenError:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Token has been revoked.",
        )
    except firebase_admin.auth.InvalidIdTokenError:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Token is invalid.",
        )
    except Exception:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Authentication failed.",
        )


def get_current_user(
    claims: dict[str, Any] = Depends(verify_firebase_token),
) -> User:
    email = claims.get("email")
    display_name = claims.get("name")
    photo_url = claims.get("picture")
    return User(
        uid=str(claims["uid"]),
        email=email if isinstance(email, str) else None,
        display_name=display_name if isinstance(display_name, str) else None,
        photo_url=photo_url if isinstance(photo_url, str) else None,
    )
