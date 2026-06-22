# Juris Phase 1 — Master Plan Index

> **For agentic workers:** This is the index. Each milestone is its own plan file in this directory. Execute milestones in order; each produces working, testable software. Use superpowers:subagent-driven-development or superpowers:executing-plans per milestone.

**Source of truth:** `docs/superpowers/specs/2026-06-22-juris-phase1-design.md`

**Goal:** Voice-first multilingual legal assistant — auth, chat with RAG, document upload/parse, voice in/out, memory, settings. Production quality, Cloud Run ready.

---

## Milestones

| # | Plan File | Produces | Depends on |
|---|---|---|---|
| M0 | `2026-06-22-juris-m0-foundation.md` | Both apps scaffold, Firebase wired, Docker/Cloud Run ready, health checks green | — |
| M1 | `juris-m1-auth.md` | Google + email/password login, session cookie, protected routes, persistence | M0 |
| M2 | `juris-m2-backend-core.md` | Pydantic models, schemas, interfaces, repos, embedding + RAG engine (unit-tested, no UI) | M0 |
| M3 | `juris-m3-documents.md` | Upload → Storage → MarkItDown → chunk → embed → Firestore | M2 |
| M4 | `juris-m4-chat-rag.md` | SSE streaming chat UI wired to RAG over uploaded docs | M2, M3 |
| M5 | `juris-m5-voice-settings.md` | Voice STT/TTS, voice UI, settings page, conversation memory sidebar | M4 |

Only M0 is written in full detail now. M1–M5 are expanded into their own plan files when reached (keeps each plan executable and prevents drift).

---

## Architecture Diagram

```
┌─────────────────────────────────────────────────────────────┐
│                      Next.js 15 (Cloud Run)                   │
│  Landing │ (auth) login/register │ (app) chat/docs/settings   │
│  features/{chat,voice,documents,memory,settings}              │
│  middleware → reads session cookie → guards (app)/*           │
└───────────────┬──────────────────────────┬──────────────────┘
                │ Bearer <id_token>         │ Firebase Auth SDK
                ▼                           ▼
┌───────────────────────────────┐   ┌──────────────────────────┐
│      FastAPI (Cloud Run)       │   │   Firebase Auth (Google) │
│  api/v1: chat, documents,      │   └──────────────────────────┘
│          voice, memory         │
│  services → interfaces → repos │
│                                │        ┌────────────────────┐
│  RAGService ─ AbstractRetrieval├───────▶│ Firestore           │
│  VoiceService ─ AbstractVoice  │        │ users/{uid}/...     │
│  DocumentService ─ MarkItDown  │        └────────────────────┘
│  LLMService ─ Gemini 2.5       │        ┌────────────────────┐
└──────┬─────────────────┬───────┘        │ Firebase Storage    │
       │                 │                 │ users/{uid}/docs/.. │
       ▼                 ▼                 └────────────────────┘
┌────────────┐   ┌─────────────────┐
│ Gemini 2.5 │   │ text-embedding- │
│ chat + TTS │   │ 004             │
└────────────┘   └─────────────────┘
```

## Dependency Map

```
Backend:
  main.py
    └─ api/v1/router.py
         ├─ chat.py ──────► services/rag_service.py ──► services/llm_service.py ──► Gemini
         │                       └─► services/embedding_service.py
         │                       └─► interfaces/retrieval.py ◄── repositories/chunk_repo.py
         │                       └─► services/memory_service.py ◄── repositories/conversation_repo.py
         ├─ documents.py ─► services/document_service.py ──► MarkItDown
         │                       └─► utils/chunking.py
         │                       └─► services/embedding_service.py
         │                       └─► repositories/{document,chunk}_repo.py
         ├─ voice.py ─────► services/voice_service.py ──► interfaces/voice.py ──► Gemini Audio/TTS
         └─ memory.py ────► services/memory_service.py
    dependencies.py ─ get_current_user (firebase-admin), get_db (firestore client)
    utils/logging.py, utils/cosine.py, config/settings.py

Frontend:
  app/(app)/layout.tsx ─ useAuth guard
    ├─ chat/[id]/page.tsx ─ useChat ─ lib/api/client.ts (SSE)
    ├─ documents/page.tsx ─ useDocuments ─ features/documents/*
    └─ settings/page.tsx ─ features/settings/*
  middleware.ts ─ session cookie check
  lib/firebase/{firebase,auth}.ts
```

## Cross-Cutting Conventions

- **Python:** 3.12+, `ruff` + `mypy --strict`, `pytest` + `pytest-asyncio`. All I/O async.
- **Files < 300 lines.** Split by responsibility.
- **No `Any` without justification comment.** Pydantic v2 models for all boundaries.
- **TypeScript `strict: true`.** No `any`. Shared types in `types/index.ts`.
- **Commits:** conventional (`feat:`, `test:`, `chore:`), one per task step.
- **Secrets:** never committed. `.env` gitignored; `.env.example` checked in.

---

See `2026-06-22-juris-m0-foundation.md` for the first executable milestone.
