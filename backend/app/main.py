"""FastAPI application factory.

Entry point for Cloud Run and local dev.  Import ``app`` for uvicorn:
    uvicorn app.main:app --reload

Create a fresh app in tests:
    from app.main import create_app
    client = TestClient(create_app())
"""
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.api.health import router as health_router
from app.config.settings import Settings, get_settings
from app.utils.logging import configure_logging, get_logger

_log = get_logger(__name__)


def register_middleware(app: FastAPI, settings: Settings) -> None:
    """Attach middleware. CORS configured from Settings.cors_origins.

    Add future middleware here (rate-limiting, request-id injection, etc.).
    Order matters: middleware registered last runs first on requests.
    """
    app.add_middleware(
        CORSMiddleware,
        allow_origins=settings.cors_origins,
        allow_credentials=True,
        allow_methods=["*"],   # Restrict to specific methods before production
        allow_headers=["*"],   # Restrict to specific headers before production
    )


def register_routes(app: FastAPI) -> None:
    """Mount all routers.

    Current routes:
        GET /health  — liveness probe

    Future routes (added in M1–M5):
        /api/v1/chat      — M4
        /api/v1/documents — M3
        /api/v1/voice     — M5
        /api/v1/memory    — M5
    """
    app.include_router(health_router)
    # api_v1_router added in M1 once auth middleware exists:
    # app.include_router(api_v1_router, prefix="/api/v1")


def register_exception_handlers(app: FastAPI) -> None:
    """Register global exception handlers.

    Populated in M2 with handlers for:
        - HTTPException  → structured JSON error response
        - RequestValidationError → 422 with field-level detail
        - RuntimeError (Firebase/Gemini misconfiguration) → 503
    """


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
    )
    register_middleware(app, settings)
    register_routes(app)
    register_exception_handlers(app)
    _log.info("app created", extra={"environment": settings.environment})
    return app


# Module-level instance for uvicorn / docker CMD.
# Tests must use create_app() directly, not this instance.
app = create_app()
