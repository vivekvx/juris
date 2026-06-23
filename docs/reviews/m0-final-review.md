# M0 Final Review

**Date:** 2026-06-23
**Branch:** main
**Commit:** 967b600

---

## Summary

M0 is complete. All infrastructure compiles, type-checks, and passes tests. No premature abstractions remain. Ready for M1.

---

## Architecture

**Backend** — FastAPI app factory (`create_app()`), 1 route (`GET /health`), settings from env, lazy Firebase accessor, JSON structured logging. Clean. No business logic yet.

**Frontend** — Next.js 16.2.9 (standalone), App Router, static pages, Zustand stores, Firebase client accessor pattern. All routes are stubs pending M1+.

**Docker** — Two services, default networking, no nginx, no DB. Backend exposes `8000:8080`, frontend `3000:3000`.

---

## Quality Checks (all passing)

| Check | Result |
|---|---|
| `uv run pytest` | 26 passed |
| `uv run mypy .` | 0 errors (strict) |
| `uv run ruff check .` | 0 warnings |
| `npm run build` | Compiled, 13 static pages |
| `npm run lint` | Clean |
| `npx tsc --noEmit` | Clean |
| `docker compose build` | Both images built |
| Backend healthcheck | 200 OK (verified via `docker exec`) |
| Frontend | 200 OK on `localhost:3000` |

---

## Image Sizes

| Image | Compressed |
|---|---|
| `juris-backend` | 499 MB |
| `juris-frontend` | 78 MB |

Backend is large due to ffmpeg (required for Gemini Native Audio). Acceptable. Frontend standalone output is lean.

---

## Issues Found and Fixed (in this commit)

| # | Issue | Fix |
|---|---|---|
| 1 | `register_exception_handlers()` empty, still called | Removed |
| 2 | M1-M5 roadmap comments in `main.py` | Removed (belong in docs) |
| 3 | Firebase comment promised lifespan init not implemented | Removed the claim |
| 4 | `NAV` array duplicated in `sidebar.tsx` and `sidebar-mobile.tsx` | Extracted to `lib/nav.ts` |
| 5 | `contextPanelOpen: true` default opens mobile drawer on load | Changed to `false` |
| 6 | `use-mobile.ts` defined but never imported | Deleted |
| 7 | `error-boundary.tsx` defined but never used | Deleted |
| 8 | `empty-state.tsx` defined but never used | Deleted |
| 9 | `shadcn` in `dependencies` (it's a CLI tool) | Moved to `devDependencies` |
| 10 | `docker-compose.yml` port was `8001:8080` | Fixed to `8000:8080` |
| 11 | `docker-compose.yml` frontend healthcheck hit `0.0.0.0` | Fixed to `localhost` |
| 12 | `depends_on: condition: service_healthy` (over-engineered) | Simplified to `depends_on: - backend` |

---

## Known Issues (not blocking M1)

### Port 8000 host conflict

`curl localhost:8000/health` hits a different service (CiteMind) because a Python process is also bound to `localhost:8000` on the dev machine. The juris-backend container **is healthy** — verified via `docker exec`. Stop CiteMind before exposing juris-backend on port 8000, or temporarily remap to `8001:8080` locally.

### Auth pages are stubs

`/auth/login` and `/auth/signup` display placeholder text. Intentional for M0. Firebase auth implementation is M1 scope.

### Context panel is empty

`ContextPanelDesktop` and `ContextPanelMobile` render empty bodies. Intentional. Sources/Timeline/Files/Memories are M3+ scope.

### Input bar sends nowhere

`InputBar.handleSubmit()` clears the textarea but doesn't dispatch to any API. Intentional — conversation API is M4 scope.

### MessageGroup is a thin wrapper

`MessageGroup` → `MessageBubble` with padding only. Will grow when threading/grouping logic arrives in M1. Not premature enough to remove.

---

## Intentional M0 Decisions to Preserve in M1

- App factory pattern (`create_app`) must stay — tests depend on it
- `get_settings()` uses `@lru_cache` — do not change to module-level global
- Firebase accessors are lazy, not initialized at startup — add lifespan hook in M1 when first route needs Firebase
- `allow_methods=["*"]` and `allow_headers=["*"]` in CORS — narrow before any auth route lands
- `google_api_key` and firebase settings have empty string defaults — intentional for M0, validate at startup in M1 when needed
- All frontend pages are static (`○`) — will shift to dynamic when auth/API connects

---

## What's Next (M1 scope — do not start without review)

- Firebase Auth: login, signup, session token, protected routes
- FastAPI lifespan hook to eagerly initialize Firebase
- First API route with auth dependency
- Narrow CORS from wildcard to specific methods/headers
- Frontend: wire auth state, redirect unauthenticated users
