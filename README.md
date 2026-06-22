# Juris

Law that listens. Truth that lasts.

Voice-first multilingual legal assistant. Phase 1.

## Stack
Next.js 15 · FastAPI · Firestore · Firebase Storage/Auth · Gemini 2.5 · Cloud Run

## Prerequisites
- Docker 24+
- `cp backend/.env.example backend/.env` and fill in values
- `cp frontend/.env.example frontend/.env.local` and fill in values

## Local dev
```bash
docker compose up --build
```
Backend: http://localhost:8000/health · Frontend: http://localhost:3000

## Layout
- `backend/` — FastAPI service
- `frontend/` — Next.js app
- `docs/superpowers/` — specs and plans
