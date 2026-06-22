"""Health check router.

Dependency-free by design — no Firebase, no Gemini, no DB.
Returns immediately so liveness/readiness probes stay fast.
"""
from fastapi import APIRouter
from pydantic import BaseModel

from app.config.settings import get_settings

router = APIRouter(tags=["health"])


class HealthResponse(BaseModel):
    status: str
    service: str


@router.get("/health", response_model=HealthResponse)
async def health() -> HealthResponse:
    """Liveness probe. Returns 200 when the process is running."""
    return HealthResponse(status="ok", service=get_settings().app_name)
