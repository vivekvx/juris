# M4 Chat + RAG — Architecture Design

**Date:** 2026-06-24  
**Status:** DRAFT — awaiting human approval  
**Scope:** RAG pipeline, Gemini streaming, SSE, conversation document scoping, title auto-generation, frontend chat wiring  
**Out of scope:** Voice STT/TTS (M5), settings page (M5), Vertex AI Matching Engine  
**Depends on:** M3 — `documents/{id}/chunks/`, `indexed_at` gate, `embed_query()`, `cosine_top_k()`

---

## 1. Message Endpoint Extension

**Decision: Extend `POST /api/conversations/{id}/messages` in-place**

M2 stored the user message and returned 201 JSON. M4 changes the response to a streaming SSE response:

```
POST /api/conversations/{id}/messages
  Body:    { content: str, document_ids?: list[str] }
  Returns: text/event-stream  ← M4 change
```

**Why SSE over WebSocket?**  
One-directional streaming per request. SSE is stateless, works over HTTP/1.1, no handshake upgrade. Legal Q&A has a clear request/response shape — WebSocket bidirectionality is unnecessary overhead.

**Why not block and return JSON?**  
Gemini 2.5 Flash response latency is 2–10 seconds for legal analysis. SSE streams tokens as they arrive.

**Stream event protocol:**

```
event: token
data: {"text": "The indemnification clause"}

event: token
data: {"text": " in Section 7.2 states..."}

event: citations
data: {"citations": [{...ChunkCitation}, ...]}

event: done
data: {"message_id": "msg-abc", "title_updated": false}

event: error
data: {"detail": "Gemini API error"}
```

`citations` is sent once after the full response streams, before `done`. Frontend appends citation cards on receipt.

---

## 2. RAG Service

**New file: `app/services/rag.py`**

```
User message content
  ↓
embed_query(content, task_type="RETRIEVAL_QUERY")
  ↓
load_chunks_for_user(uid)          ← collection group query (M3 index required)
  ↓
cosine_top_k(query, chunks, top_k=settings.retrieval_top_k,
             doc_ids=conversation.document_ids,
             score_threshold=settings.citation_score_threshold)
  ↓
build_context(ranked_chunks)       ← numbered source blocks for Gemini prompt
  ↓
build_messages(history[-10:], context, user_content)
  ↓
client.aio.models.generate_content_stream(model="gemini-2.5-flash", ...)
  ↓
yield SSE tokens → accumulate → write assistant message to Firestore
```

**Context window budget:**

| Component | Est. tokens |
|-----------|-------------|
| System prompt | ~300 |
| Retrieved chunks (5 × 512) | ~2,560 |
| Conversation history (last 10 messages) | ~3,000 |
| User message | ~200 |
| **Total input** | ~6,060 |

Gemini 2.5 Flash context: 1,048,576 tokens. No truncation logic needed in M4.

**When no indexed docs exist:**  
Proceed without retrieval context. System prompt instructs Gemini to answer from general legal knowledge and disclose. `citations` event fires with empty array.

---

## 3. System Prompt

```python
SYSTEM_PROMPT = """You are Juris, an AI legal assistant. You help users understand
legal documents and answer questions about their legal matters.

Core principles:
- Cite sources inline using [1], [2], ... when drawing on provided documents
- If no document sources are relevant, say so explicitly
- Never fabricate legal citations, case law, or statutes
- Respond in the same language as the user's question
- Flag when a question requires a licensed attorney's judgment

When document context is provided, prioritize it over general knowledge.
When document context is absent or insufficient, answer from general legal
knowledge and state clearly that no uploaded documents were referenced."""
```

**Multilingual:** No explicit language detection needed. Gemini 2.5 Flash natively handles Hindi, Kannada, Tamil, Telugu. The instruction "respond in the same language" is sufficient.

**Temperature:** `0.3` — lower than default to reduce hallucination risk for legal content.

---

## 4. Conversation Model Extension

**Additive fields (M3 schema unchanged):**

```python
class Conversation(BaseModel):
    # ... M2 fields unchanged ...
    document_ids:    list[str] | None = None   # None = all user's indexed docs
    title_generated: bool = False              # True after auto-title set
```

`document_ids: None` means retrieve from all user's indexed documents. Frontend context panel sets this when user pins specific documents to a conversation.

**New route:**

```
PATCH /api/conversations/{id}
  Body:    { document_ids?: list[str] | null, title?: str }
  Returns: 200 ConversationResponse
```

`document_ids: null` resets to "all docs" mode. Each ID is validated as belonging to the requesting user (ownership check in service layer).

---

## 5. Message Persistence

Write both messages after stream completes — user message before streaming, assistant message after:

```
messages/{msg_id_user}/
  role:       "user"
  content:    str
  citations:  null
  created_at: datetime UTC Z

messages/{msg_id_asst}/
  role:       "assistant"
  content:    str            ← full accumulated text
  citations:  list[dict]     ← serialized ChunkCitation list (from M3 model)
  created_at: datetime UTC Z
```

**Write ordering:**

1. Write user message → update `conversations/{id}/last_message_at` (single batch)
2. Begin SSE stream
3. Accumulate tokens
4. On stream close (success or error): write assistant message

On Gemini error mid-stream: write accumulated text + `"\n\n[Response interrupted]"`, send `event: error`.

---

## 6. Title Auto-Generation

After the first assistant response (`title_generated == False`), fire-and-forget a separate Gemini call:

```python
async def generate_title(user_msg: str, assistant_msg: str) -> str:
    response = await client.aio.models.generate_content(
        model="gemini-2.5-flash",
        contents=f"User: {user_msg[:200]}\nAssistant: {assistant_msg[:200]}",
        config={"system_instruction": "Generate a 5-word title for this legal conversation. Respond with only the title, no punctuation.", "max_output_tokens": 20},
    )
    return response.text.strip()
```

Write title to `conversations/{id}/title`, set `title_generated: True`. Non-blocking — runs after SSE closes. Failure is silently ignored; user-provided title remains.

**Cost:** ~200 input + ~10 output tokens = ~$0.00002/conversation. Negligible.

---

## 7. Gemini Streaming API

```python
response = await client.aio.models.generate_content_stream(
    model="gemini-2.5-flash",
    contents=messages,
    config=types.GenerateContentConfig(
        system_instruction=SYSTEM_PROMPT,
        temperature=0.3,
        max_output_tokens=2048,
    ),
)
async for chunk in response:
    if chunk.text:
        yield chunk.text
```

`max_output_tokens=2048` caps response length and cost. Legal explanations rarely exceed this.

---

## 8. SSE Route

**New file: `app/api/chat.py`** — takes over `POST /{id}/messages` from `conversations.py`

```python
@router.post("/{conversation_id}/messages")
async def send_message(...) -> StreamingResponse:
    return StreamingResponse(
        _stream_rag_response(conversation_id, body, current_user),
        media_type="text/event-stream",
        headers={"Cache-Control": "no-cache", "X-Accel-Buffering": "no"},
    )
```

`X-Accel-Buffering: no` prevents nginx/Cloud Run from buffering the SSE stream.

**Route conflict:** `conversations.py` currently owns `POST /{id}/messages`. In M4, that route is removed from `conversations.py` and replaced in `chat.py`. All other conversation CRUD stays in `conversations.py`.

---

## 9. Frontend Changes

**SSE consumption — `useChat.ts` rewrite:**

```typescript
// EventSource does NOT support POST or custom auth headers.
// Use fetch + ReadableStream + manual SSE parsing.
const response = await fetch(`/api/conversations/${id}/messages`, {
  method: "POST",
  body: JSON.stringify({ content, document_ids }),
  headers: {
    "Content-Type": "application/json",
    "Authorization": `Bearer ${idToken}`,
  },
});
const reader = response.body!.getReader();
// parse "event: X\ndata: {...}\n\n" blocks manually
```

**New components:**

```
features/chat/
  StreamingMessage.tsx   ← renders partial text while tokens arrive
  CitationCard.tsx       ← collapsible source card (filename, page, excerpt, score)

features/documents/
  ContextPanel.tsx       ← update: "Attach to conversation" toggle per READY doc
```

**Document polling:**  
`GET /api/documents` every 3 seconds while any doc has `status == PROCESSING`. Stop when all READY or FAILED. Existing context panel already filters by READY; polling makes new uploads appear without refresh.

---

## 10. Failure Handling

```
Stage               │ Failure                          │ Response
────────────────────┼──────────────────────────────────┼─────────────────────────────────
embed_query         │ Gemini API error                 │ SSE error event; no messages written
load_chunks         │ Firestore error                  │ Proceed without context; log warning
Gemini stream       │ Error mid-stream                 │ Write partial message; SSE error event
Gemini stream       │ Safety filter triggered          │ SSE error: "Response blocked by safety filter"
Title generation    │ Any error                        │ Silently skip; title unchanged
PATCH conversation  │ Invalid document_id (not owned)  │ 404 per non-owned resource policy
```

---

## 11. New Files

```
backend/app/
  api/
    chat.py              ← SSE streaming endpoint
  services/
    rag.py               ← retrieve → build context → Gemini stream
    llm.py               ← generate_content_stream(), generate_title() wrappers

frontend/src/
  features/chat/
    StreamingMessage.tsx
    CitationCard.tsx
  hooks/
    useChat.ts           ← rewrite for SSE
```

**Modified:**
- `app/api/conversations.py` — remove `POST /{id}/messages`; add `PATCH /{id}`
- `app/models/conversation.py` — add `document_ids`, `title_generated`
- `app/main.py` — register `chat_router`
- `frontend/features/documents/ContextPanel.tsx` — attach toggle
- `frontend/app/(app)/chat/[id]/page.tsx` — wire SSE, citations

---

## 12. M5 Compatibility

M5 adds voice (STT → text → chat, TTS from assistant response).

1. **STT output feeds `content`** — transcribed text goes into `POST /{id}/messages` unchanged
2. **TTS reads completed response** — `POST /api/voice/synthesize` called with accumulated assistant text after `done` event. No chat API changes.
3. **Citations ignored by voice** — TTS skips citation metadata. No schema conflict.

No M4 decisions need revision for M5 compatibility.

---

## 13. Summary of Decisions

| Area | Decision | Reason |
|------|----------|--------|
| Streaming protocol | SSE via `fetch` + ReadableStream | `EventSource` doesn't support POST or auth headers |
| Endpoint change | `POST /{id}/messages` returns `text/event-stream` | Same URL; SSE replaces JSON response |
| Route separation | Send-message moves to `chat.py` | Separates RAG from conversation CRUD |
| Gemini model | `gemini-2.5-flash` | Fast, cheap; 1M context; sufficient for legal Q&A |
| Temperature | 0.3 | Legal accuracy; low hallucination risk |
| History window | Last 10 messages | ~5 exchanges; ample for legal continuity |
| No-document behavior | Proceed without context | Don't gate chat on having docs |
| Title generation | Fire-and-forget after first reply | Non-blocking; UX improvement, not a feature gate |
| `document_ids: None` | All indexed docs | Safe default; per-conversation scoping is opt-in |
| Partial message on error | Write accumulated text + interrupted marker | Better than empty; user sees partial useful answer |
| Citation event | Sent after full stream, before `done` | Avoids interleaving with token events |
