"""Embedding service — wraps google-genai text-embedding-004.

Batch size: 100 texts per API call (SDK limit).
Retry: 3 attempts with exponential backoff on 429/503.
"""
from __future__ import annotations

import asyncio
import logging
from itertools import islice
from typing import Any, Iterator

from google import genai

from app.config.settings import get_settings

_log = logging.getLogger(__name__)
_MODEL = "text-embedding-004"
_BATCH_SIZE = 100
_RETRYABLE_STATUS_CODES = {429, 503}


def _batched(iterable: list[str], n: int) -> Iterator[list[str]]:
    it = iter(iterable)
    while batch := list(islice(it, n)):
        yield batch


def _get_client() -> genai.Client:
    return genai.Client(api_key=get_settings().google_api_key)


def _is_retryable(exc: Exception) -> bool:
    code = getattr(exc, "code", None) or getattr(exc, "status_code", None)
    try:
        return int(code) in _RETRYABLE_STATUS_CODES  # type: ignore[arg-type]
    except (TypeError, ValueError):
        return False


async def _embed_batch(client: genai.Client, texts: list[str], task_type: str) -> list[list[float]]:
    for attempt in range(3):
        try:
            response = await client.aio.models.embed_content(
                model=_MODEL,
                contents=texts,  # type: ignore[arg-type]  # SDK accepts list[str]
                config={"task_type": task_type},
            )
            embeddings: list[Any] = response.embeddings or []
            return [list(e.values) for e in embeddings]
        except Exception as exc:
            if not _is_retryable(exc) or attempt == 2:
                raise
            wait = 2 ** (attempt + 1)
            _log.warning("Embedding API error %s; retry %d/3 in %ds", exc, attempt + 1, wait)
            await asyncio.sleep(wait)
    raise RuntimeError("unreachable")  # pragma: no cover


async def embed_chunks(texts: list[str]) -> list[list[float]]:
    """Embed chunk texts for indexing (RETRIEVAL_DOCUMENT task type)."""
    client = _get_client()
    embeddings: list[list[float]] = []
    batches = list(_batched(texts, _BATCH_SIZE))
    for i, batch in enumerate(batches):
        embeddings.extend(await _embed_batch(client, batch, "RETRIEVAL_DOCUMENT"))
        if i < len(batches) - 1:
            await asyncio.sleep(0.1)  # courtesy rate-limit guard between batches
    return embeddings


async def embed_query(text: str) -> list[float]:
    """Embed a single query string for retrieval (RETRIEVAL_QUERY task type)."""
    client = _get_client()
    results = await _embed_batch(client, [text], "RETRIEVAL_QUERY")
    return results[0]
