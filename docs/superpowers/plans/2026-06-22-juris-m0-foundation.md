# Juris M0 — Foundation Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Scaffold both apps with a green health check, structured config, Firebase wiring (lazy), and Cloud Run–ready Docker images — nothing feature-specific yet.

**Architecture:** Monorepo (`backend/` FastAPI + `frontend/` Next.js 15). Backend uses Pydantic-settings for typed config and lazy Firebase Admin init so tests run without credentials. Frontend uses App Router + Tailwind + shadcn/ui. Each app has its own Dockerfile targeting Cloud Run (PORT env, single process).

**Tech Stack:** FastAPI, Pydantic v2, pydantic-settings, firebase-admin, pytest; Next.js 15, TypeScript, Tailwind, shadcn/ui.

---

## File Structure (created in M0)

```
Juris/
├── .gitignore
├── README.md
├── docker-compose.yml
├── backend/
│   ├── pyproject.toml
│   ├── Dockerfile
│   ├── .env.example
│   ├── app/
│   │   ├── __init__.py
│   │   ├── main.py                 # FastAPI app + /health
│   │   ├── config/
│   │   │   ├── __init__.py
│   │   │   └── settings.py         # Settings(BaseSettings)
│   │   ├── core/
│   │   │   ├── __init__.py
│   │   │   └── firebase.py         # lazy admin app + firestore client
│   │   └── utils/
│   │       ├── __init__.py
│   │       └── logging.py          # structured JSON logger
│   └── tests/
│       ├── __init__.py
│       ├── conftest.py
│       ├── test_health.py
│       └── test_settings.py
└── frontend/
    ├── package.json                # via create-next-app
    ├── Dockerfile
    ├── .env.example
    ├── next.config.ts              # output: "standalone"
    ├── tsconfig.json
    ├── components.json             # shadcn
    ├── app/{layout.tsx,page.tsx,globals.css}
    └── lib/firebase/firebase.ts
```

---

## Task 1: Repo hygiene

**Files:**
- Create: `Juris/.gitignore`
- Create: `Juris/README.md`

- [ ] **Step 1: Write `.gitignore`**

```gitignore
# Python
__pycache__/
*.py[cod]
.venv/
.pytest_cache/
.mypy_cache/
.ruff_cache/
# Node
node_modules/
.next/
out/
# Env & secrets
.env
.env.local
*-service-account*.json
firebase-credentials.json
# OS
.DS_Store
```

- [ ] **Step 2: Write `README.md`**

````markdown
# Juris

Law that listens. Truth that lasts.

Voice-first multilingual legal assistant. Phase 1.

## Stack
Next.js 15 · FastAPI · Firestore · Firebase Storage/Auth · Gemini 2.5 · Cloud Run

## Local dev
```bash
docker compose up --build
```
Backend: http://localhost:8000/health · Frontend: http://localhost:3000

## Layout
- `backend/` — FastAPI service
- `frontend/` — Next.js app
- `docs/superpowers/` — specs and plans
````

- [ ] **Step 3: Commit**

```bash
cd /Users/vivek/Juris
git add .gitignore README.md
git commit -m "chore: repo hygiene — gitignore and README"
```

---

## Task 2: Backend project + typed settings

**Files:**
- Create: `backend/pyproject.toml`
- Create: `backend/app/__init__.py` (empty)
- Create: `backend/app/config/__init__.py` (empty)
- Create: `backend/app/config/settings.py`
- Create: `backend/tests/__init__.py` (empty)
- Create: `backend/tests/test_settings.py`
- Create: `backend/.env.example`

- [ ] **Step 1: Write `pyproject.toml`**

```toml
[project]
name = "juris-backend"
version = "0.1.0"
requires-python = ">=3.12"
dependencies = [
    "fastapi>=0.115",
    "uvicorn[standard]>=0.34",
    "pydantic>=2.10",
    "pydantic-settings>=2.7",
    "firebase-admin>=6.6",
    "google-genai>=0.8",
    "markitdown[all]>=0.1.6",
    "numpy>=2.1",
    "python-multipart>=0.0.18",
]

[project.optional-dependencies]
dev = ["pytest>=8.3", "pytest-asyncio>=0.25", "httpx>=0.28", "mypy>=1.14", "ruff>=0.9"]

[tool.pytest.ini_options]
asyncio_mode = "auto"
testpaths = ["tests"]

[tool.ruff]
line-length = 100
target-version = "py312"

[tool.mypy]
python_version = "3.12"
strict = true
```

- [ ] **Step 2: Write `app/config/settings.py`**

```python
"""Typed application configuration loaded from environment."""
from functools import lru_cache

from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    """Environment-backed settings. Secrets never have defaults."""

    model_config = SettingsConfigDict(env_file=".env", extra="ignore")

    app_name: str = "juris-backend"
    environment: str = "development"
    cors_origins: list[str] = ["http://localhost:3000"]

    google_api_key: str = ""
    firebase_project_id: str = ""
    firebase_credentials: str = ""  # path to service account JSON
    firebase_storage_bucket: str = ""

    # Optional observability (no-op until set)
    langfuse_secret_key: str = ""
    langfuse_public_key: str = ""


@lru_cache
def get_settings() -> Settings:
    """Cached singleton so env is parsed once."""
    return Settings()
```

- [ ] **Step 3: Write `tests/test_settings.py`**

```python
from app.config.settings import Settings


def test_defaults_are_safe():
    s = Settings(_env_file=None)
    assert s.app_name == "juris-backend"
    assert s.environment == "development"
    assert s.google_api_key == ""  # no secret leaks via default


def test_env_override(monkeypatch):
    monkeypatch.setenv("GOOGLE_API_KEY", "test-key")
    assert Settings(_env_file=None).google_api_key == "test-key"
```

- [ ] **Step 4: Write `.env.example`**

```bash
ENVIRONMENT=development
GOOGLE_API_KEY=
FIREBASE_PROJECT_ID=
FIREBASE_CREDENTIALS=./firebase-credentials.json
FIREBASE_STORAGE_BUCKET=
LANGFUSE_SECRET_KEY=
LANGFUSE_PUBLIC_KEY=
```

- [ ] **Step 5: Install and run tests**

Run:
```bash
cd /Users/vivek/Juris/backend
python3.12 -m venv .venv && . .venv/bin/activate
pip install -e ".[dev]"
pytest tests/test_settings.py -v
```
Expected: 2 passed.

- [ ] **Step 6: Commit**

```bash
git add backend/pyproject.toml backend/app backend/tests backend/.env.example
git commit -m "feat(backend): typed settings with pydantic-settings"
```

---

## Task 3: Structured logging util

**Files:**
- Create: `backend/app/utils/__init__.py` (empty)
- Create: `backend/app/utils/logging.py`
- Create: `backend/tests/test_logging.py`

- [ ] **Step 1: Write the failing test `tests/test_logging.py`**

```python
import json

from app.utils.logging import configure_logging, get_logger


def test_logger_emits_json(capsys):
    configure_logging()
    get_logger("test").info("hello", extra={"uid": "u1"})
    err = capsys.readouterr().err
    record = json.loads(err.strip().splitlines()[-1])
    assert record["message"] == "hello"
    assert record["level"] == "INFO"
    assert record["uid"] == "u1"
```

- [ ] **Step 2: Run to verify it fails**

Run: `pytest tests/test_logging.py -v`
Expected: FAIL — `ModuleNotFoundError: app.utils.logging`.

- [ ] **Step 3: Write `app/utils/logging.py`**

```python
"""Structured JSON logging to stderr (Cloud Run captures stderr)."""
import json
import logging
import sys
from typing import Any

_RESERVED = set(logging.LogRecord("", 0, "", 0, "", (), None).__dict__)


class _JsonFormatter(logging.Formatter):
    def format(self, record: logging.LogRecord) -> str:
        payload: dict[str, Any] = {
            "level": record.levelname,
            "logger": record.name,
            "message": record.getMessage(),
        }
        for key, value in record.__dict__.items():
            if key not in _RESERVED and not key.startswith("_"):
                payload[key] = value
        return json.dumps(payload)


def configure_logging(level: int = logging.INFO) -> None:
    handler = logging.StreamHandler(sys.stderr)
    handler.setFormatter(_JsonFormatter())
    root = logging.getLogger()
    root.handlers.clear()
    root.addHandler(handler)
    root.setLevel(level)


def get_logger(name: str) -> logging.Logger:
    return logging.getLogger(name)
```

- [ ] **Step 4: Run to verify it passes**

Run: `pytest tests/test_logging.py -v`
Expected: PASS.

- [ ] **Step 5: Commit**

```bash
git add backend/app/utils backend/tests/test_logging.py
git commit -m "feat(backend): structured JSON logging"
```

---

## Task 4: Lazy Firebase Admin init

**Files:**
- Create: `backend/app/core/__init__.py` (empty)
- Create: `backend/app/core/firebase.py`
- Create: `backend/tests/test_firebase.py`

Rationale: Firebase must not initialize at import time, or tests and `--help` break without credentials. Lazy singleton.

- [ ] **Step 1: Write the failing test `tests/test_firebase.py`**

```python
from app.core import firebase


def test_get_firestore_without_creds_raises(monkeypatch):
    # No credentials configured → clear, early error, not an import crash.
    monkeypatch.setattr(firebase, "_app", None)
    monkeypatch.setattr(firebase.get_settings(), "firebase_credentials", "")
    try:
        firebase.get_firestore()
        raised = False
    except RuntimeError as exc:
        raised = "FIREBASE_CREDENTIALS" in str(exc)
    assert raised
```

- [ ] **Step 2: Run to verify it fails**

Run: `pytest tests/test_firebase.py -v`
Expected: FAIL — `ModuleNotFoundError: app.core.firebase`.

- [ ] **Step 3: Write `app/core/firebase.py`**

```python
"""Lazy Firebase Admin initialization. No side effects at import time."""
from __future__ import annotations

import firebase_admin
from firebase_admin import credentials, firestore, storage

from app.config.settings import get_settings

_app: firebase_admin.App | None = None


def _ensure_app() -> firebase_admin.App:
    global _app
    if _app is not None:
        return _app
    settings = get_settings()
    if not settings.firebase_credentials:
        raise RuntimeError("FIREBASE_CREDENTIALS is not set; cannot init Firebase.")
    cred = credentials.Certificate(settings.firebase_credentials)
    _app = firebase_admin.initialize_app(
        cred, {"storageBucket": settings.firebase_storage_bucket}
    )
    return _app


def get_firestore() -> firestore.Client:
    return firestore.client(_ensure_app())


def get_bucket() -> storage.storage.Bucket:
    return storage.bucket(app=_ensure_app())
```

- [ ] **Step 4: Run to verify it passes**

Run: `pytest tests/test_firebase.py -v`
Expected: PASS.

- [ ] **Step 5: Commit**

```bash
git add backend/app/core backend/tests/test_firebase.py
git commit -m "feat(backend): lazy Firebase Admin init"
```

---

## Task 5: FastAPI app + health endpoint

**Files:**
- Create: `backend/app/main.py`
- Create: `backend/tests/conftest.py`
- Create: `backend/tests/test_health.py`

- [ ] **Step 1: Write the failing test `tests/test_health.py`**

```python
from fastapi.testclient import TestClient

from app.main import create_app


def test_health_ok():
    client = TestClient(create_app())
    resp = client.get("/health")
    assert resp.status_code == 200
    body = resp.json()
    assert body["status"] == "ok"
    assert body["service"] == "juris-backend"
```

- [ ] **Step 2: Write `tests/conftest.py`**

```python
import pytest

from app.utils.logging import configure_logging


@pytest.fixture(autouse=True)
def _logging():
    configure_logging()
```

- [ ] **Step 3: Run to verify it fails**

Run: `pytest tests/test_health.py -v`
Expected: FAIL — `cannot import name 'create_app'`.

- [ ] **Step 4: Write `app/main.py`**

```python
"""FastAPI application factory."""
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.config.settings import get_settings
from app.utils.logging import configure_logging


def create_app() -> FastAPI:
    configure_logging()
    settings = get_settings()
    app = FastAPI(title=settings.app_name, version="0.1.0")

    app.add_middleware(
        CORSMiddleware,
        allow_origins=settings.cors_origins,
        allow_credentials=True,
        allow_methods=["*"],
        allow_headers=["*"],
    )

    @app.get("/health")
    async def health() -> dict[str, str]:
        return {"status": "ok", "service": settings.app_name}

    return app


app = create_app()
```

- [ ] **Step 5: Run to verify it passes**

Run: `pytest tests/test_health.py -v`
Expected: PASS.

- [ ] **Step 6: Run the full suite + type check**

Run:
```bash
pytest -v
mypy app
ruff check app
```
Expected: all tests pass, mypy clean, ruff clean.

- [ ] **Step 7: Commit**

```bash
git add backend/app/main.py backend/tests/conftest.py backend/tests/test_health.py
git commit -m "feat(backend): FastAPI app factory with health endpoint"
```

---

## Task 6: Backend Dockerfile (Cloud Run ready)

**Files:**
- Create: `backend/Dockerfile`

- [ ] **Step 1: Write `backend/Dockerfile`**

```dockerfile
FROM python:3.12-slim AS base
ENV PYTHONUNBUFFERED=1 PIP_NO_CACHE_DIR=1
WORKDIR /app

# System deps for markitdown (ffmpeg for audio)
RUN apt-get update && apt-get install -y --no-install-recommends \
    ffmpeg \
    && rm -rf /var/lib/apt/lists/*

COPY pyproject.toml ./
RUN pip install --upgrade pip && pip install -e .

COPY app ./app

# Cloud Run injects PORT; default 8080
ENV PORT=8080
CMD ["sh", "-c", "uvicorn app.main:app --host 0.0.0.0 --port ${PORT}"]
```

- [ ] **Step 2: Build to verify**

Run:
```bash
cd /Users/vivek/Juris/backend
docker build -t juris-backend:dev .
docker run --rm -p 8080:8080 -d --name juris-be juris-backend:dev
sleep 3 && curl -s localhost:8080/health && docker stop juris-be
```
Expected: `{"status":"ok","service":"juris-backend"}`.

- [ ] **Step 3: Commit**

```bash
git add backend/Dockerfile
git commit -m "chore(backend): Cloud Run Dockerfile"
```

---

## Task 7: Frontend scaffold (Next.js 15 + Tailwind + shadcn)

**Files:**
- Create: `frontend/` (via create-next-app)
- Create: `frontend/components.json` (via shadcn init)
- Modify: `frontend/next.config.ts` (add `output: "standalone"`)

- [ ] **Step 1: Scaffold Next.js 15**

Run:
```bash
cd /Users/vivek/Juris
npx create-next-app@latest frontend \
  --typescript --tailwind --eslint --app --no-src-dir \
  --import-alias "@/*" --use-npm --yes
```
Expected: `frontend/` created with `app/`, `package.json`, Tailwind configured.

- [ ] **Step 2: Init shadcn/ui**

Run:
```bash
cd /Users/vivek/Juris/frontend
npx shadcn@latest init -d
npx shadcn@latest add button card input
```
Expected: `components.json`, `components/ui/{button,card,input}.tsx`, `lib/utils.ts` created.

- [ ] **Step 3: Set standalone output in `next.config.ts`**

```typescript
import type { NextConfig } from "next";

const nextConfig: NextConfig = {
  output: "standalone",
};

export default nextConfig;
```

- [ ] **Step 4: Replace `app/page.tsx` with a placeholder landing**

```tsx
export default function Home() {
  return (
    <main className="flex min-h-screen flex-col items-center justify-center gap-4">
      <h1 className="text-4xl font-semibold tracking-tight">Juris</h1>
      <p className="text-muted-foreground">Law that listens. Truth that lasts.</p>
    </main>
  );
}
```

- [ ] **Step 5: Verify build + lint**

Run:
```bash
npm run lint
npm run build
```
Expected: lint clean, build succeeds (`.next/standalone` produced).

- [ ] **Step 6: Commit**

```bash
cd /Users/vivek/Juris
git add frontend
git commit -m "feat(frontend): Next.js 15 + Tailwind + shadcn scaffold"
```

---

## Task 8: Frontend Firebase client + env example

**Files:**
- Create: `frontend/lib/firebase/firebase.ts`
- Create: `frontend/.env.example`

- [ ] **Step 1: Install Firebase**

Run:
```bash
cd /Users/vivek/Juris/frontend
npm install firebase
```

- [ ] **Step 2: Write `lib/firebase/firebase.ts`**

```typescript
import { getApp, getApps, initializeApp, type FirebaseApp } from "firebase/app";
import { getAuth, type Auth } from "firebase/auth";

const config = {
  apiKey: process.env.NEXT_PUBLIC_FIREBASE_API_KEY,
  authDomain: process.env.NEXT_PUBLIC_FIREBASE_AUTH_DOMAIN,
  projectId: process.env.NEXT_PUBLIC_FIREBASE_PROJECT_ID,
  storageBucket: process.env.NEXT_PUBLIC_FIREBASE_STORAGE_BUCKET,
  messagingSenderId: process.env.NEXT_PUBLIC_FIREBASE_MESSAGING_SENDER_ID,
  appId: process.env.NEXT_PUBLIC_FIREBASE_APP_ID,
};

export const firebaseApp: FirebaseApp = getApps().length ? getApp() : initializeApp(config);
export const auth: Auth = getAuth(firebaseApp);
```

- [ ] **Step 3: Write `frontend/.env.example`**

```bash
NEXT_PUBLIC_FIREBASE_API_KEY=
NEXT_PUBLIC_FIREBASE_AUTH_DOMAIN=
NEXT_PUBLIC_FIREBASE_PROJECT_ID=
NEXT_PUBLIC_FIREBASE_STORAGE_BUCKET=
NEXT_PUBLIC_FIREBASE_MESSAGING_SENDER_ID=
NEXT_PUBLIC_FIREBASE_APP_ID=
NEXT_PUBLIC_API_URL=http://localhost:8000
```

- [ ] **Step 4: Verify it compiles**

Run: `npm run build`
Expected: build succeeds (empty env at build time is fine — client init is lazy at runtime).

- [ ] **Step 5: Commit**

```bash
cd /Users/vivek/Juris
git add frontend/lib/firebase frontend/.env.example
git commit -m "feat(frontend): Firebase client init"
```

---

## Task 9: Frontend Dockerfile (Cloud Run ready)

**Files:**
- Create: `frontend/Dockerfile`

- [ ] **Step 1: Write `frontend/Dockerfile`**

```dockerfile
FROM node:20-slim AS deps
WORKDIR /app
COPY package.json package-lock.json ./
RUN npm ci

FROM node:20-slim AS builder
WORKDIR /app
COPY --from=deps /app/node_modules ./node_modules
COPY . .
RUN npm run build

FROM node:20-slim AS runner
WORKDIR /app
ENV NODE_ENV=production
COPY --from=builder /app/.next/standalone ./
COPY --from=builder /app/.next/static ./.next/static
COPY --from=builder /app/public ./public
ENV PORT=8080
EXPOSE 8080
CMD ["node", "server.js"]
```

- [ ] **Step 2: Build to verify**

Run:
```bash
cd /Users/vivek/Juris/frontend
docker build -t juris-frontend:dev .
```
Expected: image builds (standalone server bundled).

- [ ] **Step 3: Commit**

```bash
git add frontend/Dockerfile
git commit -m "chore(frontend): Cloud Run Dockerfile"
```

---

## Task 10: docker-compose for local dev

**Files:**
- Create: `Juris/docker-compose.yml`

- [ ] **Step 1: Write `docker-compose.yml`**

```yaml
services:
  backend:
    build: ./backend
    ports:
      - "8000:8080"
    env_file:
      - ./backend/.env
    volumes:
      - ./backend/app:/app/app

  frontend:
    build: ./frontend
    ports:
      - "3000:8080"
    env_file:
      - ./frontend/.env
    depends_on:
      - backend
```

- [ ] **Step 2: Verify config parses**

Run:
```bash
cd /Users/vivek/Juris
docker compose config
```
Expected: merged config prints without error.

- [ ] **Step 3: Commit**

```bash
git add docker-compose.yml
git commit -m "chore: docker-compose for local dev"
```

---

## Definition of Done (M0)

- `pytest -v` green; `mypy app` and `ruff check app` clean.
- `curl localhost:8000/health` → `{"status":"ok","service":"juris-backend"}`.
- `npm run build` produces `.next/standalone`.
- Both Docker images build; `docker compose config` valid.
- No secrets committed; `.env.example` files present for both apps.

---

## Self-Review

- **Spec coverage:** M0 covers "Cloud Run deployment readiness", scaffold for feature-first structure, Firebase wiring, observability env stub. Auth/chat/voice/docs/RAG/memory/settings deferred to M1–M5 by design.
- **Placeholder scan:** none — every step has runnable content.
- **Type consistency:** `get_settings()` singleton used uniformly; `create_app()` factory name matches test import; `firebaseApp`/`auth` exports match future M1 usage.
