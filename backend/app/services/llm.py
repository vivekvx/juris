"""Gemini LLM wrappers: streaming response + title generation."""
from __future__ import annotations

import logging
from collections.abc import AsyncGenerator

from google import genai
from google.genai import types

from app.config.settings import get_settings
from app.models.conversation import Message

_log = logging.getLogger(__name__)

_MODEL = "gemini-2.5-flash"

SYSTEM_PROMPT = """You are Juris, an AI legal assistant. You help users understand \
legal documents and answer questions about their legal matters.

Core principles:
- Cite sources inline using [1], [2], ... when drawing on provided documents
- If no document sources are relevant, say so explicitly
- Never fabricate legal citations, case law, or statutes
- Respond in the same language as the user's question
- Flag when a question requires a licensed attorney's judgment

When document context is provided between [DOCUMENTS] and [/DOCUMENTS], prioritize it \
over general knowledge. When no documents are provided or none are relevant, answer from \
general legal knowledge and state clearly that no uploaded documents were referenced."""


def _get_client() -> genai.Client:
    return genai.Client(api_key=get_settings().google_api_key)


def _build_contents(history: list[Message], context: str, user_content: str) -> list[dict[str, object]]:
    msgs: list[dict[str, object]] = []
    for msg in history:
        role = "model" if msg.role == "assistant" else "user"
        msgs.append({"role": role, "parts": [{"text": msg.content}]})
    final = f"{context}\n\nQuestion: {user_content}" if context else user_content
    msgs.append({"role": "user", "parts": [{"text": final}]})
    return msgs


async def stream_response(
    history: list[Message],
    context: str,
    user_content: str,
) -> AsyncGenerator[str, None]:
    client = _get_client()
    contents = _build_contents(history, context, user_content)
    response = await client.aio.models.generate_content_stream(
        model=_MODEL,
        contents=contents,  # type: ignore[arg-type]
        config=types.GenerateContentConfig(
            system_instruction=SYSTEM_PROMPT,
            temperature=0.3,
            max_output_tokens=2048,
        ),
    )
    async for chunk in response:
        if chunk.text:
            yield chunk.text


async def generate_title(user_msg: str, assistant_msg: str) -> str:
    client = _get_client()
    response = await client.aio.models.generate_content(
        model=_MODEL,
        contents=f"User: {user_msg[:200]}\nAssistant: {assistant_msg[:200]}",
        config=types.GenerateContentConfig(
            system_instruction="Generate a 5-word title for this legal conversation. Respond with only the title, no punctuation.",
            max_output_tokens=20,
        ),
    )
    return (response.text or "").strip()
