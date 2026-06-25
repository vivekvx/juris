"""FastAPI application factory.

Entry point for Cloud Run and local dev.  Import ``app`` for uvicorn:
    uvicorn app.main:app --reload

Create a fresh app in tests:
    from app.main import create_app
    client = TestClient(create_app())
"""
from contextlib import asynccontextmanager
from typing import AsyncGenerator

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.api.chat import router as chat_router
from app.api.conversations import router as conversations_router
from app.api.documents import router as documents_router
from app.api.health import router as health_router
from app.api.ledger import router as ledger_router
from app.api.users import router as users_router
from app.api.voice import router as voice_router
from app.config.settings import Settings, get_settings
from app.utils.logging import configure_logging, get_logger

_log = get_logger(__name__)


@asynccontextmanager
async def lifespan(app: FastAPI) -> AsyncGenerator[None, None]:
    """Recover documents stuck in PROCESSING from a previous crashed instance."""
    try:
        from app.services.documents import recover_stuck_documents
        recovered = recover_stuck_documents(timeout_minutes=10)
        if recovered:
            _log.warning("Recovered %d stuck documents at startup", recovered)
    except Exception as exc:
        _log.error("Stuck document recovery failed: %s", exc)
    yield


def register_middleware(app: FastAPI, settings: Settings) -> None:
    app.add_middleware(
        CORSMiddleware,
        allow_origins=settings.cors_origins,
        allow_credentials=True,
        allow_methods=["GET", "POST", "PATCH", "DELETE"],
        allow_headers=["Content-Type", "Authorization"],
    )


def register_routes(app: FastAPI) -> None:
    app.include_router(health_router)
    app.include_router(users_router)
    app.include_router(documents_router)
    app.include_router(conversations_router)
    app.include_router(chat_router)
    app.include_router(voice_router)
    app.include_router(ledger_router)


def create_app() -> FastAPI:
    """Application factory. Creates a configured FastAPI instance.

    Call once at startup (uvicorn) or once per test (TestClient).
    Never call at module import time — keep side-effect free.
    """
    configure_logging()
    settings = get_settings()
    app = FastAPI(
        title=settings.app_name,
        version="0.1.0",
        docs_url="/docs",
        redoc_url="/redoc",
        lifespan=lifespan,
    )
    register_middleware(app, settings)
    register_routes(app)
    _log.info("app created", extra={"environment": settings.environment})
    return app


# Module-level instance for uvicorn / docker CMD.
# Tests must use create_app() directly, not this instance.
app = create_app()
