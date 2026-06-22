# Juris — Phase 1 Design Spec

**Date:** 2026-06-22
**Tagline:** Law that listens. Truth that lasts.
**Philosophy:** AI assists. AI verifies. Humans decide.
**Priority:** Trust > Accuracy > Explainability > Accessibility > Automation

---

## Scope

Phase 1 only. Future phases (citation verification, lawyer dashboard, escalation, podcast, WhatsApp) are explicitly out of scope.

Phase 1 delivers:
1. Authentication (Google + email/password via Firebase Auth)
2. Home / landing page
3. Chat interface with streaming
4. Voice input (STT via Gemini Native Audio)
5. Voice output (TTS via Gemini Native Audio, base64 JSON)
6. Document upload (PDF, DOCX, images → Firebase Storage)
7. Document parsing (MarkItDown → structured markdown)
8. Basic RAG (Firestore-only, cosine similarity, no vector DB)
9. Memory foundation (conversation + document history in Firestore)
10. Settings page

---

## Tech Stack

| Layer | Technology |
|---|---|
| Frontend | Next.js 15 App Router, TypeScript, Tailwind CSS, shadcn/ui |
| Backend | FastAPI, Python 3.12+, Pydantic v2 |
| Database | Firestore |
| Storage | Firebase Storage |
| Auth | Firebase Auth |
| LLM | Gemini 2.5 (chat + streaming) |
| Embeddings | Gemini text-embedding-004 |
| Voice | Gemini Native Audio (STT + TTS) |
| Parsing | MarkItDown |
| Deployment | Cloud Run |
| Observability | Langfuse-ready stub (no-op until env var set) |

---

## Architecture

### Auth Flow

```
Frontend (Firebase Auth) → Google / email+password → Firebase ID Token
→ Authorization: Bearer <token> → FastAPI dependency
→ firebase-admin.auth().verify_id_token(token) → uid
→ All handlers receive verified uid
```

Protected routes in Next.js: a `/api/auth/session` route exchanges the Firebase ID token for an httpOnly session cookie (via `firebase-admin`). Next.js middleware reads this cookie and redirects unauthenticated requests to `/login`. Backend API calls still send `Authorization: Bearer <id_token>` and are verified independently by FastAPI.

### Frontend Structure

```
frontend/
├── app/
│   ├── page.tsx                  # Landing page (hero, features, how-it-works, languages, footer)
│   ├── layout.tsx                # Root layout, theme provider
│   ├── (auth)/
│   │   ├── login/page.tsx
│   │   └── register/page.tsx
│   └── (app)/                    # Protected layout with auth guard
│       ├── layout.tsx            # Sidebar + top nav
│       ├── chat/
│       │   ├── page.tsx          # New chat
│       │   └── [id]/page.tsx     # Conversation by ID
│       ├── documents/page.tsx
│       └── settings/page.tsx
├── components/
│   └── ui/                       # shadcn/ui components
├── features/
│   ├── chat/
│   │   ├── MessageList.tsx
│   │   ├── MessageBubble.tsx
│   │   ├── ChatInput.tsx
│   │   ├── StreamingText.tsx
│   │   └── TypingIndicator.tsx
│   ├── voice/
│   │   ├── VoiceRecorder.tsx
│   │   ├── VoicePlayer.tsx
│   │   └── LanguageDetector.tsx
│   ├── documents/
│   │   ├── UploadZone.tsx
│   │   ├── DocumentCard.tsx
│   │   └── ParseStatus.tsx
│   ├── memory/
│   │   └── ConversationSidebar.tsx
│   └── settings/
│       ├── ThemeToggle.tsx
│       ├── LanguageSelect.tsx
│       └── ProfileSection.tsx
├── lib/
│   ├── firebase/
│   │   ├── firebase.ts
│   │   └── auth.ts
│   └── api/
│       └── client.ts
├── hooks/
│   ├── useAuth.ts
│   ├── useChat.ts
│   ├── useVoice.ts
│   └── useDocuments.ts
└── types/
    └── index.ts
```

### Backend Structure

```
backend/
├── app/
│   ├── main.py
│   ├── dependencies.py
│   ├── api/v1/
│   │   ├── router.py
│   │   ├── chat.py
│   │   ├── documents.py
│   │   ├── voice.py
│   │   └── memory.py
│   ├── services/
│   │   ├── llm_service.py
│   │   ├── rag_service.py
│   │   ├── embedding_service.py
│   │   ├── document_service.py
│   │   ├── voice_service.py
│   │   └── memory_service.py
│   ├── repositories/
│   │   ├── base.py
│   │   ├── conversation_repo.py
│   │   ├── document_repo.py
│   │   └── chunk_repo.py
│   ├── interfaces/
│   │   ├── retrieval.py          # AbstractRetrievalBackend protocol
│   │   └── voice.py              # AbstractVoiceBackend protocol
│   ├── models/
│   │   ├── conversation.py
│   │   ├── document.py
│   │   ├── chunk.py
│   │   └── user.py
│   ├── schemas/
│   │   ├── chat.py
│   │   ├── document.py
│   │   └── voice.py
│   └── utils/
│       ├── chunking.py
│       ├── cosine.py
│       └── logging.py
└── tests/
    ├── test_rag.py
    ├── test_document.py
    └── test_voice.py
```

### Firestore Data Model

```
users/{uid}/
  conversations/{conv_id}/
    metadata:
      title: str
      created_at: timestamp
      updated_at: timestamp
      language: str
    messages/{msg_id}/
      role: "user" | "assistant"
      content: str
      timestamp: timestamp
      language: str
      has_audio: bool
  documents/{doc_id}/
    metadata:
      name: str
      size: int
      mime_type: str
      storage_path: str
      parsed_at: timestamp
      chunk_count: int
    chunks/{chunk_id}/
      text: str
      embedding: float[]
      page: int | None
      chunk_index: int
```

---

## Key Flows

### Chat with RAG

```
User message
  → POST /api/v1/chat (conv_id, optional doc_ids)
  → embed query (text-embedding-004)
  → load user chunks from Firestore
  → cosine_similarity(query_embedding, chunk_embeddings)
  → top-5 chunks as context
  → system prompt (legal assistant + language instruction)
  → Gemini 2.5 stream
  → SSE response to frontend
  → save messages to Firestore
```

### Voice Input

```
User clicks mic → MediaRecorder → Blob (webm/opus)
  → POST /api/v1/voice/transcribe (multipart)
  → Gemini Native Audio STT
  → { text, language }
  → injected into chat input
```

### Voice Output

```
User clicks speak
  → POST /api/v1/voice/synthesize { text, language }
  → Gemini Native Audio TTS
  → { text, audio_base64, language }
  → frontend: base64 → AudioContext playback + waveform
```

### Document Upload

```
User drops file
  → client validates type + size
  → upload to Firebase Storage: users/{uid}/documents/{doc_id}/{filename}
  → POST /api/v1/documents/upload { storage_path, name, mime_type }
  → backend downloads from Storage
  → MarkItDown.convert() → markdown
  → chunk (500 tokens / 50 overlap)
  → embed each chunk (text-embedding-004)
  → store in Firestore chunks subcollection
  → return { doc_id, chunk_count, parsed_preview }
```

---

## Interface Contracts

### AbstractRetrievalBackend

```python
# backend/app/interfaces/retrieval.py
from typing import Protocol
from app.models.chunk import Chunk

class AbstractRetrievalBackend(Protocol):
    async def store_chunks(self, uid: str, doc_id: str, chunks: list[Chunk]) -> None: ...
    async def retrieve(self, uid: str, query_embedding: list[float], top_k: int) -> list[Chunk]: ...
    async def delete_document(self, uid: str, doc_id: str) -> None: ...
```

Phase 1: `FirestoreRetrievalBackend` (load all + cosine in Python)
Phase 2+: `VertexMatchingEngineBackend` | `QdrantBackend` — same interface

### AbstractVoiceBackend

```python
# backend/app/interfaces/voice.py
from typing import Protocol

class AbstractVoiceBackend(Protocol):
    async def transcribe(self, audio_bytes: bytes, mime_type: str) -> TranscriptionResult: ...
    async def synthesize(self, text: str, language: str) -> VoiceResult: ...
```

Phase 1: returns `audio_base64` in JSON
Phase 2+: streaming audio/mpeg | WebRTC — same interface, different payload

---

## Retrieval Strategy

- Phase 1: load all user chunks, cosine similarity in Python (numpy). Acceptable up to ~200 chunks.
- Perceptible degradation around ~500 chunks — trigger for Firestore Vector Search migration.
- No premature optimization.

---

## Observability Stub

```python
async def _trace(name: str, fn):
    if settings.LANGFUSE_SECRET_KEY:
        # real Langfuse trace
        ...
    else:
        return await fn()
```

Enable: set `LANGFUSE_SECRET_KEY` + `LANGFUSE_PUBLIC_KEY`.

---

## Supported Languages

| Code | Language |
|---|---|
| en | English |
| hi | Hindi |
| kn | Kannada |
| ta | Tamil |
| te | Telugu |
| mixed | Code-switched (respond in dominant language) |

---

## Design Principles

1. Clean architecture — services never import from API layer
2. Interfaces before implementations — retrieval and voice are protocols
3. Pydantic v2 everywhere — models, schemas, settings
4. Async everywhere — no sync I/O in request path
5. Files under 300 lines
6. No TODOs, no mocks — working code or nothing
7. Correctness first, scale later

---

## Out of Scope

- Citation verification
- Lawyer dashboard
- Escalation
- Podcast
- WhatsApp
- Vertex AI Matching Engine / Qdrant
- Streaming audio output / WebRTC

---

## Environment Variables

```bash
# Backend
GOOGLE_API_KEY=
FIREBASE_PROJECT_ID=
FIREBASE_CREDENTIALS=        # path to service account JSON
FIREBASE_STORAGE_BUCKET=
LANGFUSE_SECRET_KEY=         # optional
LANGFUSE_PUBLIC_KEY=         # optional

# Frontend (.env.local)
NEXT_PUBLIC_FIREBASE_API_KEY=
NEXT_PUBLIC_FIREBASE_AUTH_DOMAIN=
NEXT_PUBLIC_FIREBASE_PROJECT_ID=
NEXT_PUBLIC_FIREBASE_STORAGE_BUCKET=
NEXT_PUBLIC_FIREBASE_MESSAGING_SENDER_ID=
NEXT_PUBLIC_FIREBASE_APP_ID=
NEXT_PUBLIC_API_URL=
```
