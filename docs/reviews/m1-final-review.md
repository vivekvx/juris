# M1 Final Review

**Date:** 2026-06-23  
**Reviewer:** Staff Engineer Review (Claude Sonnet 4.6)  
**Status:** APPROVED — ready to tag

---

## Architecture Summary

```
UI (LoginCard / SignupCard)
  ↓
useAuth()                        ← typed AuthContextValue, no Firebase types
  ↓
AuthProvider.createSession()     ← atomic: Firebase auth → session cookie → backend profile
  ↓
POST /api/auth/session           ← Next.js route handler, sets __session cookie
  ↓
Session Cookie (__session)       ← httpOnly, sameSite=strict, 7 days
  ↓
app/(protected)/layout.tsx       ← server component, single auth guard
  ↓ (on protected routes)
lib/session.ts → lib/current-user.ts  ← Firebase Admin verifySessionCookie(checkRevoked=true)
  ↓
FastAPI POST /api/users/me       ← Bearer token, Depends(get_current_user)
  ↓
Firestore users/{uid}            ← profile, language preference, timestamps
```

---

## Key Decisions

### Server Component guards instead of middleware

`middleware.ts` runs on every request including static assets, API routes, and
Next.js internals. Auth failures in middleware produce cryptic redirects for
non-page requests. The `app/(protected)/layout.tsx` guard runs only for routes
that require auth, fails clearly via `redirect("/auth/login")`, and composes
naturally with the server-component data model.

### Session cookies instead of ID-token cookies

Firebase ID tokens expire in 1 hour and require client-side refresh. A session
cookie issued by Firebase Admin (`createSessionCookie`) can be set to 7 days,
is verified server-side with `verifySessionCookie`, and never requires the
client to hold a live Firebase session after login. This makes auth restoration
(refresh, browser reopen) silent and instantaneous.

### Firebase identity separated from Firestore profile

Firebase Auth owns identity: email, display name, photo, UID. Firestore owns
application state: preferred language, created_at, updated_at. The separation
means the app profile can evolve independently of Firebase Auth fields. It also
avoids embedding application metadata in custom claims.

### Fail-closed philosophy

Every auth failure returns 401 (never 403). `HTTPBearer(auto_error=False)`
ensures a missing header returns 401, not a 403 from FastAPI's default
credential validation. Session creation failures roll back Firebase sign-in
immediately. Profile init failures roll back both Firebase and the session
cookie. Partial auth state is never allowed to persist.

### Strong typing

- `types/user.ts` — app-level User type; no Firebase types cross this boundary
- `AuthContextValue` — fully typed context interface; consumers never touch Firebase
- Backend `User` model — Pydantic v2 strict; no `Any` in models or routes
- `dict[str, Any]` confined to Firebase/Firestore SDK boundaries (unavoidable)

---

## Tradeoffs

**Why middleware was rejected:**  
Middleware auth requires matching path patterns, which is fragile. Adding a new
protected route requires updating the middleware matcher. The layout guard is
co-located with the route group and has zero configuration surface.

**Why `verifySessionCookie(checkRevoked=True)` was chosen:**  
Firebase allows token revocation (password change, account disable). Without
`checkRevoked=True`, a revoked session remains valid until natural expiry (7
days). The performance cost (one Firebase network call per server render) is
acceptable for a security boundary. This is the right default for a legal
product.

**Why Firestore owns metadata:**  
Auth claims are limited in size and have a sync delay. Firestore supports
arbitrary fields, real-time queries, and granular security rules. Application
metadata belongs in application storage.

---

## Technical Debt

**Real debt only — no wishes:**

1. **No DELETE /api/users/me** — no way to hard-delete a user account. Requires
   both Firestore deletion and Firebase Auth deletion. Left for a dedicated
   account management task.

2. **`verifySessionCookie` makes a network call every server render** — Firebase
   Admin SDK caches the public keys but the revocation check is live. Under high
   traffic this will be a hot path. Mitigation: short-circuit on CDN-cached
   pages, or add a session-level cache with a 60s TTL.

3. **`backendPost` only covers POST** — `lib/api.ts` has no `backendGet`. Fine
   for M1 which has one backend call. Will need to extend before adding
   GET-heavy features.

4. **`uv.lock` modified but not committed** — the lock file has unstaged changes
   from package sync. Should be committed with infrastructure changes.

---

## Risks

**Auth complexity:**  
Three systems coordinate during sign-in (Firebase Auth, Next.js session cookie,
FastAPI backend). Any network failure mid-flow triggers a rollback. The rollback
is tested but runs sequentially — a slow DELETE /api/auth/session delays the
error surface to the user.

**Session lifecycle:**  
7-day session cookies are never refreshed. A user who signs in on day 1 and
stays logged in until day 7 will hit an abrupt session expiry. No graceful
re-auth flow exists yet (no "session expired" UX). This is M2 territory but
should not be forgotten.

**Firebase typing limitations:**  
`firebase_admin` has no py.typed marker. All Firebase SDK boundary code uses
`dict[str, Any]` with explicit field extraction. A type-safe Firebase Admin
wrapper library would eliminate this debt, but none exists for Python.

---

## Lessons Learned

**Successful patterns:**

- `getApps().length > 0` check for HMR-safe Firebase Admin singleton — prevents
  duplicate app initializations in Next.js dev mode without module-level globals
- `AuthContext` pattern with null-check in `useAuth()` — fails loudly when used
  outside the provider, not silently at runtime
- Application factory in FastAPI (`create_app()`) — made testing clean; each
  test gets a fresh app with dependency overrides, no shared state
- `cast(DocumentSnapshot, ref.get())` — minimal workaround for Firestore sync
  client mypy stub issue without disabling strict checks globally

**Mistakes avoided:**

- Did not use `middleware.ts` for auth — would have required pattern matching and
  broken API route handling
- Did not store session tokens in localStorage — avoids XSS exposure
- Did not use Firebase ID tokens as session tokens — avoids 1-hour refresh churn
- Did not let Firebase types leak into UI layer — `AuthContextValue` exposes
  `User` (app type), not `FirebaseUser`

**Architectural wins:**

- Single auth boundary at `app/(protected)/layout.tsx` — one place to audit,
  one place to update
- Fail-closed rollback chain — partial auth state never persists across steps
- Backend completely independent of Next.js session mechanism — can be called
  from any client with a valid Firebase ID token

---

## M2 Preparation

**Upload pipeline:**  
M2 will introduce document ingestion. Uploads go through the backend (not
direct-to-storage from the client) so the backend can validate file type, size,
and ownership before writing to Cloud Storage. A `POST /api/documents/upload`
endpoint accepts multipart form data, stores to Cloud Storage, and writes a
Firestore record to `documents/{doc_id}` with owner UID and metadata.

**Storage:**  
Cloud Storage bucket with per-user path prefix: `users/{uid}/documents/{doc_id}`.
Signed URLs issued by the backend for download — client never holds raw storage
credentials.

**APIs:**  
- `POST /api/documents/upload` — multipart, returns document metadata
- `GET /api/documents` — list documents for authenticated user
- `DELETE /api/documents/{doc_id}` — soft delete (marks `deleted_at`, does not
  purge storage immediately)
- Backend will need `backendGet` and `backendDelete` added to `lib/api.ts`

---

## Quality Gates

All gates green at time of review:

| Gate | Result |
|------|--------|
| `npm test -- --run` | 38/38 pass |
| `npm run lint` | clean |
| `npx tsc --noEmit` | clean |
| `npm run build` | clean |
| `uv run pytest` | 67/67 pass |
| `uv run mypy . --strict` | clean |
| `uv run ruff check .` | clean |
