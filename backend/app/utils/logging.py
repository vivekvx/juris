"""Structured JSON logging for Juris backend.

Every log record is emitted as a JSON object to stderr.
Cloud Run captures stderr as structured logs automatically.

Usage:
    from app.utils.logging import configure_logging, get_logger, set_request_id

    configure_logging()          # call once at app startup (idempotent)
    set_request_id("req-abc")   # set per-request in FastAPI middleware

    log = get_logger(__name__)
    log.info("document parsed", extra={"doc_id": "d1", "chunk_count": 42})

Note: request_id propagates automatically to asyncio tasks (copy_context semantics).
It does NOT propagate to threads created via ThreadPoolExecutor — bind manually there.
"""
from __future__ import annotations

import json
import logging
import sys
from contextvars import ContextVar
from datetime import UTC, datetime
from typing import Any

# ---------------------------------------------------------------------------
# Request context — async-safe via contextvars
# ---------------------------------------------------------------------------

_request_id: ContextVar[str | None] = ContextVar("request_id", default=None)


def set_request_id(value: str) -> None:
    """Bind a request ID to the current async context."""
    _request_id.set(value)


def get_request_id() -> str | None:
    """Return the request ID for the current async context, or None."""
    return _request_id.get()


# ---------------------------------------------------------------------------
# Formatter
# ---------------------------------------------------------------------------

# Fields that belong to LogRecord internals — never copied into JSON payload.
_RESERVED: frozenset[str] = frozenset(
    logging.LogRecord("", 0, "", 0, "", (), None).__dict__
)


class JsonFormatter(logging.Formatter):
    """Formats log records as single-line JSON objects.

    Subclass and override ``build_payload`` to add custom fields
    (e.g. Langfuse trace IDs, audit metadata) without changing callers.
    """

    def build_payload(self, record: logging.LogRecord) -> dict[str, Any]:
        """Return the base payload. Override to extend."""
        payload: dict[str, Any] = {
            "timestamp": datetime.now(UTC).strftime("%Y-%m-%dT%H:%M:%S.%f")[:-3] + "Z",
            "level": record.levelname,
            "logger": record.name,
            "message": record.getMessage(),
        }
        # Attach request_id when present in async context
        rid = get_request_id()
        if rid is not None:
            payload["request_id"] = rid
        # Attach caller-supplied extra fields
        for key, value in record.__dict__.items():
            if key not in _RESERVED and not key.startswith("_"):
                payload[key] = value
        return payload

    def format(self, record: logging.LogRecord) -> str:
        return json.dumps(self.build_payload(record))


# ---------------------------------------------------------------------------
# Public API
# ---------------------------------------------------------------------------

def configure_logging(
    level: int = logging.INFO,
    formatter: logging.Formatter | None = None,
) -> None:
    """Configure root logger to emit JSON to stderr.

    Replaces all existing root-logger handlers on each call. Safe to call at app startup and in tests.
    Pass a custom ``formatter`` to replace JsonFormatter (e.g. for Langfuse).
    """
    root = logging.getLogger()
    root.handlers.clear()  # We own the root logger; clear all before reconfiguring.
    handler = logging.StreamHandler(sys.stderr)
    handler.setFormatter(formatter or JsonFormatter())
    root.addHandler(handler)
    root.setLevel(level)


def get_logger(name: str) -> logging.Logger:
    """Return a logger by name. Call configure_logging() first."""
    return logging.getLogger(name)
