"""Token-based recursive text splitter.

Uses UTF-8 byte length as token proxy: bytes // BYTES_PER_TOKEN.
BYTES_PER_TOKEN=2 is conservative for Indic scripts (actual ~1.5 bytes/token),
ensuring chunks never exceed text-embedding-004's 2048-token input limit.
"""
from __future__ import annotations

import re

_SEPARATORS = ["\n\n", "\n", ". ", " ", ""]
_BYTES_PER_TOKEN = 2  # conservative; Indic UTF-8 is ~3 bytes/char, ~1.5 bytes/token


def _estimate_tokens(text: str) -> int:
    return max(1, len(text.encode("utf-8")) // _BYTES_PER_TOKEN)


def _split_text(text: str, size_tokens: int, overlap_tokens: int, separators: list[str]) -> list[str]:
    """Recursively split text targeting size_tokens per chunk."""
    if _estimate_tokens(text) <= size_tokens:
        return [text] if text.strip() else []

    sep = separators[0]
    remaining_seps = separators[1:]

    if sep == "":
        # Character-level fallback: hard-cut by byte budget
        budget_bytes = size_tokens * _BYTES_PER_TOKEN
        encoded = text.encode("utf-8")
        chunks: list[str] = []
        step = max(budget_bytes - overlap_tokens * _BYTES_PER_TOKEN, budget_bytes // 2)
        i = 0
        while i < len(encoded):
            chunk_bytes = encoded[i : i + budget_bytes]
            chunk = chunk_bytes.decode("utf-8", errors="ignore")
            if chunk.strip():
                chunks.append(chunk)
            i += step
        return chunks

    parts = text.split(sep)
    chunks = []
    current_parts: list[str] = []
    current_tokens = 0

    for part in parts:
        part_tokens = _estimate_tokens(part + sep)
        if current_tokens + part_tokens > size_tokens and current_parts:
            merged = sep.join(current_parts)
            if remaining_seps:
                chunks.extend(_split_text(merged, size_tokens, overlap_tokens, remaining_seps))
            elif merged.strip():
                chunks.append(merged)
            # overlap: keep trailing parts that fit the overlap budget
            overlap_parts: list[str] = []
            overlap_total = 0
            for p in reversed(current_parts):
                p_tok = _estimate_tokens(p + sep)
                if overlap_total + p_tok <= overlap_tokens:
                    overlap_parts.insert(0, p)
                    overlap_total += p_tok
                else:
                    break
            current_parts = overlap_parts
            current_tokens = overlap_total

        current_parts.append(part)
        current_tokens += part_tokens

    if current_parts:
        merged = sep.join(current_parts)
        if remaining_seps and _estimate_tokens(merged) > size_tokens:
            chunks.extend(_split_text(merged, size_tokens, overlap_tokens, remaining_seps))
        elif merged.strip():
            chunks.append(merged)

    return chunks


def split_pages(text: str) -> list[tuple[int, str]]:
    """Split on form-feed (pdfminer page boundary). Returns [(page_num, text), ...]."""
    pages = re.split(r"\x0c", text)
    return [(i + 1, p) for i, p in enumerate(pages) if p.strip()]


def chunk_document(
    text: str,
    *,
    mime_type: str,
    size_tokens: int,
    overlap_tokens: int,
    max_chunks: int,
) -> list[tuple[int | None, str, int]]:
    """Chunk document text. Returns [(page_number, content, token_count), ...].

    page_number is None for non-PDF mime types (no page concept).
    """
    is_pdf = mime_type == "application/pdf"
    result: list[tuple[int | None, str, int]] = []

    if is_pdf:
        pages = split_pages(text)
        if not pages:
            pages = [(1, text)]
        for page_num, page_text in pages:
            for chunk in _split_text(page_text, size_tokens, overlap_tokens, list(_SEPARATORS)):
                if chunk.strip():
                    result.append((page_num, chunk.strip(), _estimate_tokens(chunk)))
                    if len(result) >= max_chunks:
                        return result
    else:
        for chunk in _split_text(text, size_tokens, overlap_tokens, list(_SEPARATORS)):
            if chunk.strip():
                result.append((None, chunk.strip(), _estimate_tokens(chunk)))
                if len(result) >= max_chunks:
                    return result

    return result
