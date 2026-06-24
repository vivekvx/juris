"""AbstractRetrievalBackend protocol.

M3 implements FirestoreRetrievalBackend (in chunk_repo.py).
M4 registers it as a FastAPI dependency via RAGService.
"""
from __future__ import annotations

from typing import Protocol

from app.models.chunk import Chunk


class AbstractRetrievalBackend(Protocol):
    async def store_chunks(self, doc_id: str, chunks: list[Chunk]) -> None: ...

    async def retrieve(
        self,
        uid: str,
        query_embedding: list[float],
        top_k: int = 5,
        doc_ids: list[str] | None = None,
    ) -> list[tuple[Chunk, float]]: ...

    async def delete_chunks(self, doc_id: str) -> None: ...
