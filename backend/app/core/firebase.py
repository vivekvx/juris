"""Lazy Firebase Admin initialization.

Exposes typed accessor functions rather than module-level globals so callers
have explicit dependencies and tests can patch at a single boundary.

Usage (in FastAPI dependencies or services):
    from app.core.firebase import get_firestore_client, get_storage_bucket

    client = get_firestore_client()   # type: google.cloud.firestore.Client
    bucket = get_storage_bucket()     # type: google.cloud.storage.Bucket

Note: Call reset_firebase_app() only in tests. Never in production code.

Threading: _ensure_app() is not thread-safe during the very first call.
FastAPI's startup event (lifespan) initializes eagerly in production to avoid
the race. Tests use reset_firebase_app() in fixtures for isolation.
"""
from __future__ import annotations

from typing import cast

import firebase_admin  # type: ignore[import-untyped]
from firebase_admin import credentials, firestore, storage
from google.cloud.firestore import Client as FirestoreClient  # google-cloud-firestore ships py.typed
from google.cloud.storage import Bucket  # type: ignore[import-untyped]  # google-cloud-storage lacks stubs

from app.config.settings import get_settings

# Module-level singleton — None until first accessor call.
_app: firebase_admin.App | None = None


def _ensure_app() -> firebase_admin.App:
    """Initialize the Firebase App if not already done.

    Reads credentials path and project config from Settings.
    Raises RuntimeError if FIREBASE_CREDENTIALS is not set,
    so misconfiguration is caught immediately at the call site.
    """
    global _app
    if _app is not None:
        return _app
    settings = get_settings()
    if not settings.firebase_credentials:
        raise RuntimeError(
            "FIREBASE_CREDENTIALS is not set. "
            "Provide the path to your Firebase service account JSON file."
        )
    cred = credentials.Certificate(settings.firebase_credentials)
    _app = firebase_admin.initialize_app(
        cred,
        {
            "projectId": settings.firebase_project_id,
            "storageBucket": settings.firebase_storage_bucket,
        },
    )
    return _app


def reset_firebase_app() -> None:
    """Clear the Firebase App singleton.

    FOR TESTING ONLY. Allows tests to re-initialize with different config.
    Calls firebase_admin.delete_app() to release SDK resources.
    """
    global _app
    if _app is not None:
        firebase_admin.delete_app(_app)
        _app = None


def get_firebase_app() -> firebase_admin.App:
    """Return the initialized Firebase App.

    Raises RuntimeError if FIREBASE_CREDENTIALS is not configured.
    """
    return _ensure_app()


def get_firestore_client() -> FirestoreClient:
    """Return a Firestore client bound to the initialized Firebase App.

    Raises RuntimeError if FIREBASE_CREDENTIALS is not configured.
    """
    return cast(FirestoreClient, firestore.client(_ensure_app()))


def get_storage_bucket() -> Bucket:
    """Return the default Firebase Storage bucket.

    Raises RuntimeError if FIREBASE_CREDENTIALS is not configured.
    """
    return storage.bucket(app=_ensure_app())
