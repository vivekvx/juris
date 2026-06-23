# M2 Backend Core — Architecture Design

**Date:** 2026-06-23  
**Status:** DRAFT — awaiting human approval  
**Scope:** Document storage, upload APIs, conversation APIs, metadata, ownership, processing states  
**Out of scope:** RAG, embeddings, Gemini, audio, video

---

## 1. Storage Strategy

**Decision: Firebase Storage via `get_storage_bucket()`**

Firebase Storage is Google Cloud Storage with Firebase Auth-aware security rules layered on top. The backend already has `get_storage_bucket()` in `app/core/firebase.py`, which returns a `google.cloud.storage.Bucket` bound to the Firebase Admin SDK. No new infrastructure. No new dependencies.

All writes go through the FastAPI backend — never direct client uploads. The backend validates the file before writing to GCS. The client never holds a writable GCS credential.

```
Client → POST /api/documents (multipart) → FastAPI → validate → GCS bucket
                                                     → Firestore document record
```

GCS object path: `users/{uid}/documents/{doc_id}/{sanitized_filename}`

The UID prefix is the ownership boundary in storage. Even if a Firestore ACL check is bypassed, a user cannot enumerate another user's objects without knowing their UID.

**Why not direct client uploads (signed URLs)?**  
M2 validation (MIME type, size, magic bytes) happens server-side before the object lands in GCS. A direct client upload would require a post-upload validation step, introducing a window where an invalid file exists in storage. Server-side upload is simpler and cleaner for M2.

**Why not a separate GCS bucket outside Firebase?**  
`get_storage_bucket()` is already wired to the Firebase project's default bucket. Adding a separate GCS project would require new IAM setup, new credentials, and new settings. The Firebase bucket is GCS — same APIs, same client library.

**M3 implications:**  
When M3 adds async processing (MarkItDown → chunks → embeddings), the pipeline reads from the same GCS object path. Storage paths are stable once written. The `storage_path` field in Firestore is the contract between M2 and M3. No changes to storage layout are needed for M3.

---

## 2. Firestore Collections

### Documents

**Decision: Top-level `documents/{doc_id}`**

```
documents/
  {doc_id}/          ← auto-generated Firestore ID
    owner_uid: str
    filename: str
    ...
```

**Rejected alternative: `users/{uid}/documents/{doc_id}`**  
Subcollections tie the document ID to the user's path. Looking up a document by ID requires knowing the owner UID (or a collection group query). Admin operations and M3 pipelines that operate on documents by ID become more complex. Top-level with `owner_uid` is simpler and sufficient.

Ownership is enforced in the service layer, not the Firestore path. Every read/write checks `doc.owner_uid == current_user.uid`. A mismatch returns 404.

### Conversations

**Decision: Top-level `conversations/{conv_id}`**

Same reasoning as documents. Conversation IDs are addressable without the user's UID. M3 retrieval pipelines will query conversations by ID.

### Messages

**Decision: Subcollection `conversations/{conv_id}/messages/{msg_id}`**

Embedding messages inside the conversation document hits Firestore's 1MB document limit at roughly 10,000 short messages. Legal conversations can be long. Subcollection scales without limit, supports cursor-based pagination, and keeps the conversation document lightweight for list views.

```
conversations/
  {conv_id}/
    owner_uid: str
    title: str
    ...
    messages/
      {msg_id}/
        role: "user" | "assistant"
        content: str
        created_at: datetime
```

---

## 3. Document Metadata Model

```python
class DocumentStatus(str, Enum):
    UPLOADING  = "UPLOADING"
    PROCESSING = "PROCESSING"   # reserved for M3; never set in M2
    READY      = "READY"
    FAILED     = "FAILED"

class Document(BaseModel):
    id:                str
    owner_uid:         str
    filename:          str           # sanitized, URL-safe, used in storage path
    original_filename: str           # what the user actually uploaded
    mime_type:         str           # validated, not trusted from Content-Type
    size_bytes:        int
    status:            DocumentStatus
    storage_path:      str           # GCS object path: users/{uid}/documents/{id}/{filename}
    error_message:     str | None    # populated on FAILED only; None otherwise
    created_at:        datetime      # UTC, stored as ISO-8601 ending in Z
    updated_at:        datetime      # UTC
```

**`filename` vs `original_filename`:**  
`original_filename` is what the user sent. `filename` is the sanitized, storage-safe version (spaces → underscores, non-ASCII stripped, length capped at 200 chars). The storage path uses `filename`. The API returns both so the UI can display the original name.

**`error_message`:**  
Required for FAILED state. Without it, users have no actionable information. It is `None` for all non-FAILED states.

**Omitted fields and why:**

| Field | Why omitted |
|-------|-------------|
| `page_count` | Processing result, not metadata. M3 adds a `processing_result` map on the document. |
| `content_hash` | Useful for deduplication but no deduplication logic in M2. Add in M3. |
| `deleted_at` | M2 does hard deletes. See section 4. |
| `language` | Detected during text extraction. M3 concern. |

---

## 4. Processing States

**Four states for M2:**

```
UPLOADING  → stream being received and written to GCS
READY      → upload complete, file validated, GCS object exists
FAILED     → validation or storage error; error_message is set
PROCESSING → reserved for M3; unused in M2 flow
```

**State transitions in M2 — synchronous, within a single request:**

```
[request arrives]
      ↓
  validate Content-Type, Content-Length
      ↓
  create Firestore record → status: UPLOADING
      ↓
  stream to GCS
      ↓
  validate magic bytes on streamed content
      ↓
  success? → update status: READY
  failure? → update status: FAILED, set error_message
             delete GCS object if partially written
```

The client receives either a READY document or a FAILED document in the 201 response. No polling in M2.

**DELETING — rejected:**  
Implies async deletion. M2 deletes synchronously. A transient DELETING state adds complexity with no consumer.

**ARCHIVED — rejected:**  
No archival concept in M2. Add when the UI requires it.

**Soft delete — rejected:**  
M2 does hard deletes: Firestore record deleted then GCS object deleted, in that order. If GCS delete fails, Firestore record is restored and 503 is returned. No `deleted_at` field, no recovery flow. Premature until there is an audit requirement or a recycle bin UI.

---

## 5. Conversation Model

```python
class Conversation(BaseModel):
    id:              str
    owner_uid:       str
    title:           str             # required, non-empty; user-provided in M2
    created_at:      datetime        # UTC
    updated_at:      datetime        # UTC
    last_message_at: datetime | None # denormalized for sort; None until first message

class Message(BaseModel):
    id:         str
    role:       Literal["user", "assistant"]
    content:    str
    created_at: datetime   # UTC
```

**`title`:**  
Required, client-provided in M2. M3 adds optional auto-generation from Gemini after the first exchange. The field is already there; M3 just writes to it.

**`last_message_at`:**  
Denormalized for sorting conversation lists without reading message subcollections. Updated on every `POST /api/conversations/{id}/messages`. `None` until the first message is sent.

**Message pagination:**  
`GET /api/conversations/{id}/messages` returns messages ordered by `created_at` ascending with cursor-based pagination (`start_after` a Firestore document snapshot). Page size default: 50. Maximum: 200. No offset pagination — Firestore does not support it efficiently.

---

## 6. Upload Limits

| Constraint | M2 Value | Rationale |
|------------|----------|-----------|
| Max file size | 25 MB | Covers 99% of legal documents. Most court filings, contracts, and briefs are under 10MB. |
| Supported MIME types | `application/pdf`, `application/vnd.openxmlformats-officedocument.wordprocessingml.document`, `text/plain` | PDF primary; DOCX for drafts; TXT for transcripts and notes. |
| Max documents per user | 100 | Soft limit in service layer. Raised without a schema change. |
| Max storage per user | Not enforced in M2 | Tracked as tech debt. Enforce in M3 when quota tracking is added. |

**MIME type validation — magic bytes, not headers:**  
The `Content-Type` header is client-controlled and untrustworthy. Validate file identity from the first bytes of the stream:

| Type | Magic bytes |
|------|-------------|
| PDF | `%PDF` (hex `25 50 44 46`) |
| DOCX | `PK\x03\x04` (ZIP header) + `[Content_Types].xml` present |
| TXT | Valid UTF-8 decode of first 4KB; no binary bytes |

Reject with 422 if declared MIME does not match magic bytes.

**Audio and video — deferred:**  
Accepting audio uploads in M2 without a processing pipeline would create documents permanently stuck in FAILED. Wait until M3 adds Whisper transcription. The MIME type allowlist enforces this boundary.

---

## 7. API Surface

All routes use `Depends(get_current_user)`. Ownership checked in service layer. Non-owned resources return **404**, not 403 — the resource does not exist from the requester's perspective.

### Documents

```
POST   /api/documents
  Content-Type: multipart/form-data
  Body: file (binary)
  Returns: 201 DocumentResponse
  Errors: 413 (too large), 415 (unsupported type), 422 (magic bytes mismatch), 503 (GCS failure)

GET    /api/documents
  Returns: 200 list[DocumentResponse]
  Query: status (filter), limit (default 20, max 100), cursor (Firestore doc ID)
  Ordered by: created_at DESC

GET    /api/documents/{id}
  Returns: 200 DocumentResponse | 404

DELETE /api/documents/{id}
  Returns: 204 No Content | 404 | 503 (GCS delete failure)
  Order: delete Firestore record first, then GCS object.
  On GCS failure: restore Firestore record, return 503.
```

**No download endpoint in M2.**  
Documents are uploaded for future processing (M3). There is no M2 consumer that needs to read document content. A signed URL endpoint is the right M3 pattern — added when the client needs to display processed documents.

### Conversations

```
POST   /api/conversations
  Body: { "title": str }
  Returns: 201 ConversationResponse

GET    /api/conversations
  Returns: 200 list[ConversationResponse]
  Ordered by: last_message_at DESC NULLS LAST, then created_at DESC
  Query: limit (default 20, max 100), cursor

GET    /api/conversations/{id}
  Returns: 200 ConversationResponse | 404

DELETE /api/conversations/{id}
  Returns: 204 No Content | 404
  Deletes messages subcollection (batch) then conversation document.

POST   /api/conversations/{id}/messages
  Body: { "content": str }
  Returns: 201 MessageResponse
  Note: role is hardcoded to "user" in M2. M3 extends to trigger AI completion.

GET    /api/conversations/{id}/messages
  Returns: 200 list[MessageResponse]
  Ordered by: created_at ASC
  Query: limit (default 50, max 200), cursor
```

**Why `POST /api/conversations/{id}/messages` accepts only content (not role) in M2:**  
M2 has no AI. Accepting an arbitrary `role` from the client would allow fake `assistant` messages. The role is hardcoded to `"user"` server-side. In M3, the endpoint internally generates and writes the `assistant` message after calling Gemini — the client still sends only `content`.

### Response shapes

```python
class DocumentResponse(BaseModel):
    id:                str
    filename:          str
    original_filename: str
    mime_type:         str
    size_bytes:        int
    status:            DocumentStatus
    error_message:     str | None
    created_at:        str   # ISO-8601 UTC ending in Z
    updated_at:        str

class ConversationResponse(BaseModel):
    id:              str
    title:           str
    created_at:      str
    updated_at:      str
    last_message_at: str | None

class MessageResponse(BaseModel):
    id:         str
    role:       str
    content:    str
    created_at: str
```

`owner_uid` is never returned in API responses.

---

## 8. Background Processing

**Decision: Synchronous within the upload request**

M2 processing is: validate magic bytes, check size, stream to GCS, write Firestore record. This completes in under 2 seconds for a 25MB file on Cloud Run. No async infrastructure needed.

**Rejected alternatives:**

| Option | Why rejected for M2 |
|--------|---------------------|
| Cloud Run Jobs | Right for scheduled batch workloads; wrong for per-request validation |
| Pub/Sub | Correct for M3 fan-out to embedding workers; zero justification in M2 |
| Cloud Tasks | Queue management overhead for a sub-2-second operation |

**M3 migration path — no API changes required:**

M2 upload flow:
```
POST /api/documents → validate → write GCS → write Firestore (READY) → return 201
```

M3 upload flow:
```
POST /api/documents → validate → write GCS → write Firestore (READY) → publish Pub/Sub → return 201
                                                                              ↓
                                                        Cloud Run worker subscribes
                                                              ↓
                                                        READY → PROCESSING → READY (indexed)
```

The client receives 201 with status READY immediately in both M2 and M3. The M3 PROCESSING → READY transition is async and observable via `GET /api/documents/{id}`. The upload endpoint is unchanged.

---

## 9. Failure States

### Upload failure (client disconnects mid-stream)

GCS streaming writes are atomic: the object becomes visible only after the stream closes successfully. If the client disconnects, the stream is abandoned. GCS does not persist a partial object. The Firestore record is written **after** GCS write completes — no record is created, no cleanup needed.

Client retries with a new `POST /api/documents`.

### Corrupted file

- **Detectable corruption** (invalid magic bytes, non-ZIP DOCX): caught before GCS write. Returns 422. No storage write. No Firestore record.
- **Undetectable corruption** (valid header, corrupt body): passes M2 validation. Lands in GCS as READY. M3 processing (MarkItDown) surfaces the error and transitions to FAILED with `error_message`.

### Unsupported file type

MIME type not in allowlist. Returns 415. No GCS write. No Firestore record. Response body lists supported types.

### Storage failure (GCS write fails)

Returns 503. No Firestore record created. FastAPI exception handler logs GCS error with full context (user UID, filename, size). Client can retry.

### DELETE failure (GCS delete fails after Firestore delete)

Firestore record is restored in a compensating write. Returns 503. The document remains visible and accessible to the user. Logged for ops investigation.

### Validation matrix

```
Condition                     → HTTP     → GCS write    → Firestore write
─────────────────────────────────────────────────────────────────────────
MIME type not in allowlist    → 415      → no           → no
Content-Length > 25MB         → 413      → no           → no
Magic bytes mismatch          → 422      → no           → no
GCS write fails               → 503      → no           → no
All validations pass          → 201      → yes          → yes (READY)
Client disconnects mid-stream → (no resp)→ no           → no
```

---

## 10. M3 Compatibility

M2 produces a stable artifact: a GCS object at `storage_path` with `status: READY`. M3 consumes it without any M2 changes.

### Processing pipeline extension

```
M2
────────────────────────────────────────
Document uploaded
status: READY
storage_path: users/{uid}/documents/{id}/{filename}

M3 (additive)
────────────────────────────────────────
Pub/Sub event: document.uploaded
      ↓
Cloud Run worker
      ↓
GCS read (storage_path)  ← uses M2's storage_path unchanged
      ↓
MarkItDown → plain text
      ↓
RecursiveTextSplitter → chunks
      ↓
Gemini text-embedding-004 → embeddings
      ↓
Firestore: documents/{id}/chunks/{chunk_id}
  { content, embedding, page_number, chunk_index, created_at }
      ↓
Document status: READY (indexed_at set)
```

### Additive Firestore schema (M3, no M2 changes)

```
documents/{id}/              ← M2 schema unchanged
  chunks/{chunk_id}/         ← M3 adds subcollection
    content:       str
    embedding:     vector    ← Firestore vector search field
    page_number:   int | None
    chunk_index:   int
    created_at:    datetime
```

The M2 `DocumentResponse` gains one optional field in M3:

```python
indexed_at: datetime | None = None   # None in M2; set after embedding completes in M3
```

M2 clients that ignore unknown fields (standard Pydantic behavior) are unaffected.

### Conversation pipeline extension (M3)

`POST /api/conversations/{id}/messages` in M2 stores the user message and returns it. M3 extends the same endpoint:

1. Store user message (M2 behavior, unchanged)
2. Retrieve top-k relevant chunks via Firestore vector search
3. Build prompt with retrieved context
4. Call Gemini
5. Write assistant message to `messages` subcollection
6. Return assistant message

The endpoint URL, auth mechanism, and request shape are unchanged. Frontend that renders messages by role automatically displays AI responses in M3.

### What M2 must get right for M3

1. **`storage_path` is immutable once written** — M3 workers reference it by value; changing paths breaks the pipeline
2. **`status` field is the observable state contract** — M3 adds transitions (`PROCESSING`); never removes or renames existing ones
3. **`documents/{id}/chunks/` path is reserved** — do not create conflicting subcollections under `documents/{id}`
4. **`owner_uid` on every document and conversation** — M3 RAG queries must filter by ownership
5. **UTC timestamps ending in Z** — consistent across all Firestore writes and API responses

---

## Summary of Decisions

| Area | Decision | Key reason |
|------|----------|------------|
| Storage | Firebase Storage via existing `get_storage_bucket()` | Already wired; GCS under the hood; no new infra |
| Document collection | Top-level `documents/{id}` with `owner_uid` | Addressable by ID; M3 pipeline friendliness |
| Conversation collection | Top-level `conversations/{id}` with `owner_uid` | Same reasoning |
| Messages | Subcollection `conversations/{id}/messages/{id}` | 1MB Firestore limit; pagination |
| Processing in M2 | Synchronous within upload request | < 2s; no async infra justified |
| Soft delete | No — hard delete | No recovery UI, no audit requirement in M2 |
| Download endpoint | Not in M2 | No M2 consumer; signed URLs added in M3 |
| `PROCESSING` status | In model, never set in M2 | M3 forward compatibility |
| Message role from client | Content only; role hardcoded to `user` | No AI in M2; prevents fake assistant messages |
| Upload limits | 25MB; PDF, DOCX, TXT only | Legal document profile; audio deferred |
| Audio/video | Not in M2 | No processing pipeline; would produce permanent FAILED state |
