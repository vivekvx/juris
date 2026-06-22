"""Health check router.

Dependency-free by design — no Firebase, no Gemini, no DB.
Returns immediately so liveness/readiness probes stay fast.
"""
from fastapi import APIRouter
from fastapi.responses import JSONResponse

router = APIRouter(tags=["health"])


@router.get("/health", response_model=None)
async def health() -> JSONResponse:
    """Liveness probe. Returns 200 when the process is running."""
    return JSONResponse({"status": "ok", "service": "juris-backend"})
