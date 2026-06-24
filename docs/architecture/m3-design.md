# M3 Document Processing — Architecture Design

**Date:** 2026-06-24  
**Status:** DRAFT — awaiting human approval  
**Scope:** MarkItDown conversion, chunking, embedding, storage schema, retrieval, citations, failure handling, cost  
**Out of scope:** Chat UI, SSE streaming (M4), voice (M5), Pub/Sub infrastructure  
**Depends on:** M2 stable artifact — GCS object at `storage_path`, Firestore `documents/{id}` with `status: READY`

---

## 1. Processing Trigger

**Decision: FastAPI `BackgroundTasks`**

M2 upload currently transitions UPLOADING → PROCESSING → READY synchronously within the request for simplicity. M3 changes this:

```
POST /api/documents (unchanged URL, unchanged auth)
  → validate → write GCS → write Firestore (UPLOADING)
  → register BackgroundTask(process_document, doc_id, uid)
  → transition to PROCESSING
  → return 201 DocumentResponse (status: PROCESSING)

BackgroundTask (runs after response sent):
  → read GCS → MarkItDown → chunk → embed → write chunks
  → transition to READY (indexed_at set)
  → on any failure: transition to FAILED (error_message set)
```

Client polls `GET /api/documents/{id}` until `status` is `READY` or `FAILED`. The frontend context panel already filters by `status == READY`, so newly indexed documents appear automatically on next poll. Suggested poll interval: 3 seconds, timeout at 5 minutes.

**Why not Pub/Sub?**  
Pub/Sub is the correct production architecture (decoupled retry, dead-letter, fan-out). But Phase 1 load does not justify the setup cost: Cloud Pub/Sub topic, subscription, service account IAM, push endpoint, and Cloud Run concurrency tuning. BackgroundTasks on the same Cloud Run instance is sufficient for Phase 1. The migration path is clean — the `_process_document()` function becomes the Cloud Run Job handler body, with no logic changes.

**Why not synchronous (current M2 approach)?**  
MarkItDown + embedding for a 25MB PDF can take 15–60 seconds. Cloud Run has a 60-second default HTTP timeout. Processing within the request risks timeouts on large documents and holds connection resources. BackgroundTasks decouples latency from document size.

**State machine (M3 — no new transitions):**

```
UPLOADING → PROCESSING   ← upload handler, before returning 201
UPLOADING → FAILED       ← GCS write failure during upload
PROCESSING → READY       ← background task completes
PROCESSING → FAILED      ← background task fails at any stage
```

`READY → PROCESSING` is NOT added in M3. Re-processing route is deferred to M4.

The `UPLOADING → PROCESSING → READY` synchronous path in `upload_document()` is removed. Upload transitions to PROCESSING, registers the background task, and returns 201. The background task drives `PROCESSING → READY`.

**Stuck-job recovery:**

`processing_started_at: datetime | None` is set on the Document when it transitions to PROCESSING. A recovery check (run at startup or via a dedicated route) detects documents where `status == PROCESSING AND now - processing_started_at > 10 minutes` and transitions them to FAILED with `error_message: "Processing timed out"`. This handles Cloud Run instance termination mid-task.

---

## 2. MarkItDown Conversion Pipeline

**Input:** GCS object bytes — read via `bucket.blob(storage_path).download_as_bytes()`  
**Library:** `markitdown[all]` (already in `pyproject.toml`)  
**Output:** markdown string

```
GCS bytes
  └─ MarkItDown.convert(BytesIO(data), file_extension=ext, url=None)
       └─ PDF   → pdfminer text extraction + structure → markdown
       └─ DOCX  → python-docx headings/tables/paragraphs → markdown
       └─ TXT   → UTF-8 passthrough, minimal wrapping
  → result.text_content   (str)
```

**Page marker extraction:**  
MarkItDown's PDF backend emits `\f` form feed characters from pdfminer at page boundaries. The pipeline detects these to assign `page_number` to each chunk. TXT and DOCX have no page concept — `page_number` is `None`.

```python
def split_pages(text: str) -> list[tuple[int, str]]:
    """Returns [(page_number, page_text), ...]. Page numbers are 1-indexed."""
    pages = re.split(r"\x0c", text)
    return [(i + 1, p) for i, p in enumerate(pages) if p.strip()]
```

**Failure conditions:**

| Condition | Action |
|-----------|--------|
| GCS read fails | FAILED: "Storage read error" |
| MarkItDown raises exception | FAILED: "Text extraction failed: {exc}" |
| Extracted text is empty | FAILED: "No text content extracted" |
| Extracted text < 20 chars | FAILED: "Document appears empty or unreadable" |

Empty result is a failure, not silent success. A document with zero chunks cannot be retrieved.

---

## 3. Chunking Strategy

**Algorithm: Recursive token-based splitter**

Split on separators in order: `"\n\n"`, `"\n"`, `". "`, `" "`, `""`. The splitter tries the largest boundary first; falls back to finer splits only when a segment exceeds the token limit.

```python
CHUNK_SIZE_TOKENS    = 512   # target tokens
CHUNK_OVERLAP_TOKENS = 50    # overlap tokens
BYTES_PER_TOKEN      = 2     # conservative estimate; 1 byte/token for ASCII, 3 bytes/char for Indic UTF-8
```

Token estimation: `len(text.encode("utf-8")) // BYTES_PER_TOKEN`

**Rationale:**

- Character-based splitting fails for Indic scripts (Hindi, Kannada, Tamil, Telugu): a 1500-char chunk can exceed 2048 tokens for text encoded at 3 bytes/char. Token-based splitting with a conservative bytes-per-token ratio is safe for all supported languages without adding a tokenizer dependency.
- 512 tokens ≈ 1024 UTF-8 bytes (worst-case Indic), a coherent legal paragraph.
- 50-token overlap preserves sentence continuity at boundaries.
- `BYTES_PER_TOKEN = 2` is intentionally conservative: actual ratio for Indic is ~1.5 (UTF-8 bytes per SentencePiece token). This under-counts tokens, meaning chunks will be smaller than 512 tokens — safe, never over the 2048-token limit.
- Chunk size is a runtime constant in settings. Changing it requires re-processing all documents.

**Page awareness:**

Chunking respects page boundaries. A chunk never spans two pages. Each page's text is chunked independently, and all chunks from that page inherit the same `page_number`.

```
page 1 text → [chunk_0, chunk_1, chunk_2]   ← page_number=1
page 2 text → [chunk_3, chunk_4]             ← page_number=2
```

`chunk_index` is global across the document (0-based). `page_number` is `None` for TXT and DOCX.

**Chunk count limits:**

| Condition | Action |
|-----------|--------|
| 0 chunks after splitting | FAILED: "No chunks produced" |
| > 1000 chunks | Truncate at 1000, set `processing_warning: "truncated at 1000 chunks"` on document |

The 1000-chunk limit protects Firestore write cost and in-Python retrieval performance. At ~200 users and 20 documents each, 200k chunks is the naive ceiling before Python cosine becomes slow. Firestore Vector Search migration is the response at that point.

---

## 4. Embedding Generation

**Model:** `text-embedding-004` via `google-genai` (already in `pyproject.toml`)  
**Dimension:** 768 (model default; fixed)  
**Task types:**
- Indexing: `task_type="RETRIEVAL_DOCUMENT"`
- Query: `task_type="RETRIEVAL_QUERY"` (M4 retrieval path)

**Batching:**

Gemini `embed_content` accepts up to 100 texts per batch call. Chunks are batched in groups of 100.

```python
async def embed_chunks(texts: list[str]) -> list[list[float]]:
    embeddings = []
    for batch in batched(texts, 100):
        response = await genai_client.aio.models.embed_content(
            model="text-embedding-004",
            contents=list(batch),
            config={"task_type": "RETRIEVAL_DOCUMENT"},
        )
        embeddings.extend([e.values for e in response.embeddings])
    return embeddings
```

**Rate limits:** text-embedding-004 — 1,500 requests/min, 1M tokens/min. For a 1000-chunk document: 10 batch calls. No throttling needed for Phase 1 single-user processing. Add `asyncio.sleep(0.1)` between batches as a courtesy guard.

**Retry policy:**

```
Attempt 1 → immediate
Attempt 2 → wait 2s
Attempt 3 → wait 8s
Failure after 3 → raise, document transitions to FAILED
```

Transient 429 (quota) and 503 (upstream) trigger retries. 400 (bad input) does not.

---

## 5. Firestore Storage Schema

### Chunks subcollection (M3 adds)

```
documents/{doc_id}/
  chunks/{chunk_id}/               ← auto-generated Firestore ID
    owner_uid:      str            ← denormalized for collection group query (M4)
    doc_id:         str            ← denormalized for citation lookup (M4)
    content:        str            ← raw chunk text (stored for retrieval display)
    embedding:      list[float]    ← 768-dimensional vector
    chunk_index:    int            ← 0-based global index within document
    page_number:    int | None     ← 1-based; None for TXT/DOCX
    token_count:    int            ← estimated; len(content.encode()) // 2
    chunk_version:  int            ← 1; bump when CHUNK_SIZE_TOKENS changes
    embedding_model: str           ← "text-embedding-004"; for future migration detection
    created_at:     datetime       ← UTC, ISO-8601 Z
```

**Why store `content` alongside the embedding?**  
The retrieval path returns chunk text to the LLM as context. Re-reading from GCS on every query would be slow and costly. Chunk content is immutable once written — no update path, only delete-and-rewrite on re-processing.

**Why `list[float]` and not Firestore's native vector type?**  
Firestore native vector search requires index creation, region-specific availability, and a specific SDK query form. Phase 1 retrieval is in-Python (numpy cosine). The field is stored as a plain `list[float]` now. When migrating to Firestore vector search, the field is re-written as a `firestore.Vector` type. The chunk schema doesn't change otherwise.

### Document additions (additive — no M2 field changes)

```python
class Document(BaseModel):
    # ... all M2 fields unchanged ...
    indexed_at:            datetime | None = None   # set when PROCESSING → READY (M3)
    chunk_count:           int | None = None        # set when PROCESSING → READY (M3)
    processing_warning:    str | None = None        # set if truncated at 1000 chunks
    processing_started_at: datetime | None = None   # set when upload handler transitions to PROCESSING
```

M2 clients receive `indexed_at: null`, `chunk_count: null` — Pydantic default, no breakage.

### Write ordering

```
1. Write all chunks to documents/{doc_id}/chunks/ (batch write, 500 per Firestore batch)
2. Update document: status=READY, indexed_at=now, chunk_count=N
```

Step 2 is the commit gate. If step 1 fails, the document stays PROCESSING (then transitions to FAILED). There are no partial READY states. Chunks from a failed attempt are cleaned up before retry.

**Batch write limits:** Firestore batch write accepts 500 operations. For documents >500 chunks, use multiple sequential batches. The `indexed_at` timestamp is set only after all batches complete.

---

## 6. Retrieval Design

**Phase 1: In-Python cosine similarity**

```
Query text
  → embed_query(text, task_type="RETRIEVAL_QUERY")   → query_embedding [768]
  → load all chunks for user's READY+indexed documents from Firestore
  → numpy cosine_similarity(query_embedding, chunk_embeddings_matrix)
  → argsort descending → top_k chunks
  → return [(chunk, score), ...]
```

```python
import numpy as np

def cosine_top_k(
    query: list[float],
    chunk_matrix: np.ndarray,   # shape: (N, 768)
    k: int = 5,
) -> list[int]:
    q = np.array(query)
    q /= np.linalg.norm(q) + 1e-10
    norms = np.linalg.norm(chunk_matrix, axis=1, keepdims=True) + 1e-10
    normed = chunk_matrix / norms
    scores = normed @ q
    return np.argsort(scores)[::-1][:k].tolist()
```

**Retrieval scope:**

- Default: all user's documents where `indexed_at is not None`
- Conversation-level scoping (M4): `conversations/{id}.document_ids: list[str]` — retrieval filtered to those documents only

M3 does not implement conversation-level scoping. That field is added to the conversation model in M4.

**`top_k = 5`** — default, not configurable in M3. At 1500 chars/chunk, 5 chunks ≈ 7,500 chars ≈ ~1,900 tokens of context. Fits comfortably in Gemini 2.5 Flash's 1M token context window with room for system prompt and response.

**Performance ceiling:**  
Loading 1,000 chunks × 768 floats = 768K floats ≈ 6MB in memory. At 20 documents × 50 chunks = 1,000 chunks/user, this is acceptable. Trigger for Firestore Vector Search migration: a single user exceeds 500 chunks, causing noticeable query latency.

---

## 7. Citation Design

Every retrieved chunk carries its provenance. The RAG service returns structured source references alongside the generated response.

**Chunk citation unit:**

```python
class ChunkCitation(BaseModel):
    doc_id:            str
    original_filename: str   # denormalized from Document at retrieval time
    chunk_index:       int
    page_number:       int | None
    content:           str   # the chunk text shown in source preview
    score:             float  # cosine similarity, 0–1
```

**Inline citation format (in assistant message):**

The system prompt instructs Gemini to insert `[1]`, `[2]`, … inline when drawing on a specific source. Retrieved chunks are presented to Gemini as:

```
[1] Source: contract_v3.pdf, Page 4
"The indemnification clause under Section 7.2 states..."

[2] Source: lease_agreement.pdf, Page 12
"Tenant shall not sublet the premises without..."
```

Gemini references these by number. The assistant message is stored with a `citations` field:

```python
class Message(BaseModel):
    # ... M2 fields ...
    citations: list[ChunkCitation] | None = None  # M3 adds; None for user messages
```

**Frontend rendering (M4):**  
Citations are displayed as collapsible source cards below the assistant message. No inline hyperlinks in Phase 1 — that requires a document viewer.

**Citation honesty:**  
If no chunks exceed a similarity threshold of 0.3, the system prompt instructs Gemini to answer from general knowledge and disclose that no document sources were used. A score-filtered `citations` list (empty if all below threshold) is returned. This prevents hallucinated citations.

---

## 8. Failure Handling

### Failure surface map

```
Stage                │ Failure mode               │ Response
─────────────────────┼────────────────────────────┼──────────────────────────────────
GCS read             │ Blob not found             │ FAILED: "Source file not found"
                     │ Network timeout            │ FAILED: "Storage read timed out"
MarkItDown           │ Exception (corrupt PDF)    │ FAILED: "Text extraction failed: {e}"
                     │ Empty result               │ FAILED: "No text extracted"
Chunking             │ Zero chunks produced       │ FAILED: "No chunks produced"
                     │ >1000 chunks               │ Truncate + warning (not failure)
Embedding API        │ 429 after 3 retries        │ FAILED: "Embedding quota exceeded"
                     │ 503 after 3 retries        │ FAILED: "Embedding service unavailable"
                     │ 400 invalid input          │ FAILED: "Embedding rejected chunk: {e}"
Firestore batch write│ Exception                  │ FAILED: "Chunk storage failed" + cleanup
```

### Cleanup on failure

Before transitioning a document to FAILED, delete any partial chunks written to `documents/{doc_id}/chunks/`. Use a Firestore collection delete (batch read → batch delete).

Rationale: a FAILED document with stale chunks from a prior attempt would produce incorrect retrieval if re-processing is triggered later. Clean state on failure simplifies re-processing.

### Re-processing

A FAILED document can be re-triggered via `POST /api/documents/{id}/reprocess`. This:
1. Verifies ownership and `status == FAILED`
2. Cleans the chunks subcollection (idempotent cleanup)
3. Transitions to PROCESSING
4. Enqueues a BackgroundTask

Not implemented in the initial M3 pass; the route placeholder is noted here for M4.

### No silent failures

Every failure path sets `error_message` on the document. The frontend document card shows this message. Users can see exactly why processing failed — not just a spinner that never resolves.

---

## 9. Cost Considerations

### Embedding cost

**Model:** text-embedding-004  
**Pricing:** $0.000002 per 1K characters (Google AI pricing, June 2026)

| Document type | Pages | Est. chunks | Characters | Cost |
|---------------|-------|-------------|------------|------|
| Short contract | 5 | 15 | 22,500 | $0.000045 |
| Standard brief | 30 | 60 | 90,000 | $0.00018 |
| Large case file | 100 | 200 | 300,000 | $0.0006 |
| Max (1000 chunks) | ~330 | 1000 | 1,500,000 | $0.003 |

Embedding cost is negligible for Phase 1. No per-user quota enforcement needed at launch.

### Firestore cost

Chunk writes: $0.18 per 100K writes. 1000 chunks/document = 1000 writes = $0.0018/document.  
Chunk reads (retrieval): all chunks loaded per query. At 1,000 chunks/user × $0.06/100K reads = $0.0006/query. Acceptable for Phase 1.

**Cost inflection point:** When per-query Firestore read cost exceeds ~$0.01, migrate retrieval to Firestore Vector Search (ANN index, reads only top-k, not all chunks).

### Gemini chat cost (M4 preview)

**Model:** Gemini 2.5 Flash  
- Input: $0.075 per 1M tokens  
- Output: $0.30 per 1M tokens  

Per query with 5 chunks × 375 tokens = 1,875 context tokens + ~500 token system prompt + user message. Input ≈ 2,500 tokens = $0.0001875. Plus output (~300 tokens) = $0.00009. Total per query: ~$0.0003.

At 100 queries/day = $0.03/day. Langfuse tracing (already stubbed in settings) enables per-user cost attribution when `LANGFUSE_SECRET_KEY` is set.

### Storage cost

GCS: $0.02/GB/month. 100 documents × 10MB average = 1GB = $0.02/month. Negligible.

Firestore storage: 1,000 chunks × (1,500 chars + 768 floats × 4 bytes) = ~4.6MB/user. At $0.18/GB: negligible.

---

## 10. M4 Compatibility

### What M3 must get right for M4

1. **`ChunkCitation` schema is stable** — M4 chat endpoint reads chunks and returns citations. The `citations` field on `Message` must be present (nullable) from M3.
2. **`task_type="RETRIEVAL_QUERY"` in embedding** — The query embedding must use the same model and task type as indexed chunks. Mixing task types degrades retrieval quality.
3. **`indexed_at` is the gate** — M4 retrieval only queries documents where `indexed_at is not None`. Documents that are READY but unindexed (edge case: M2 documents uploaded before M3 deployed) are excluded from retrieval silently.
4. **Chunk content is stored verbatim** — M4 builds Gemini prompts from `chunk.content`. No post-processing applied at write time. The chunk is the unit of truth.
5. **`documents/{doc_id}/chunks/` path is the retrieval contract** — M4 queries this subcollection by `owner_uid` via collection group query. Path must not change.

### Collection group query (M4 retrieval)

```python
# Load all chunks for a user across all their documents
chunks_ref = (
    firestore_client
    .collection_group("chunks")
    .where("owner_uid", "==", uid)
    .stream()
)
```

`owner_uid` is denormalized onto each chunk (see section 5) specifically to enable this query.

### Conversation → document scoping (M4 schema prep)

M3 does not implement conversation-level document scoping. M4 adds:

```
conversations/{conv_id}/
  document_ids: list[str] | None   ← None means "all user documents"
```

No M3 work required. M4 adds this field and the retrieval filter.

### AbstractRetrievalBackend (interface)

M4 wires the retrieval pipeline through a protocol:

```python
class AbstractRetrievalBackend(Protocol):
    async def store_chunks(self, doc_id: str, chunks: list[Chunk]) -> None: ...
    async def retrieve(
        self,
        uid: str,
        query_embedding: list[float],
        top_k: int = 5,
        doc_ids: list[str] | None = None,
    ) -> list[tuple[Chunk, float]]: ...
    async def delete_chunks(self, doc_id: str) -> None: ...
```

M3 implements `FirestoreRetrievalBackend`. M4 registers it as a FastAPI dependency. The retrieval backend is not surfaced in M3 APIs — it is an internal interface used by M4's `RAGService`.

---

## 11. New Files

```
backend/app/
  services/
    processing.py         ← _process_document() BackgroundTask entry point
    embedding.py          ← embed_chunks(), embed_query() via google-genai
    chunking.py           ← recursive_split(), split_pages()
  interfaces/
    retrieval.py          ← AbstractRetrievalBackend protocol
  repositories/
    chunk_repo.py         ← write_chunks(), delete_chunks(), load_chunks()
  models/
    chunk.py              ← Chunk, ChunkCitation Pydantic models
```

Existing files modified (additive only):
- `app/models/document.py` — add `indexed_at`, `chunk_count`, `processing_warning`
- `app/api/documents.py` — upload returns PROCESSING + registers BackgroundTask
- `app/services/documents.py` — add READY→PROCESSING transition; add `update_indexed` helper
- `app/config/settings.py` — add `max_chunks_per_document: int = 1000`, `top_k: int = 5`

---

## 12. Summary of Decisions

| Area | Decision | Key reason |
|------|----------|------------|
| Trigger | FastAPI BackgroundTasks | No Pub/Sub infra needed; clean migration path later |
| Upload response | Returns `status: PROCESSING` | Async processing; client polls |
| MarkItDown | `convert(BytesIO, file_extension)` | Already installed; handles PDF/DOCX/TXT |
| Page tracking | Split on `\x0c` form feed | Enables page-level citations |
| Chunk size | 1500 chars / 150 overlap | ~375 tokens; fits embedding limit; legal paragraph granularity |
| Max chunks | 1000 per document | Protects in-Python retrieval; truncate + warn, not fail |
| Embedding model | text-embedding-004, dim=768 | Already installed; correct task types |
| Embedding batching | 100 texts/call, 3-retry with backoff | API limit; resilience |
| Chunk storage | Firestore subcollection + `list[float]` | Simple; numpy cosine works; vector search migration path clear |
| `owner_uid` on chunk | Yes, denormalized | Enables collection group query in M4 without parent lookups |
| Retrieval (Phase 1) | In-Python cosine via numpy | Already installed; fast enough to ~1000 chunks/user |
| Citation threshold | Score ≥ 0.3 to include | Prevents low-relevance hallucinated citations |
| `top_k` | 5 | ~1900 tokens of context; well within Gemini context window |
| Failure cleanup | Delete partial chunks before FAILED | Clean state enables re-processing |
| Re-processing | Route placeholder only | Full implementation deferred to M4 |
| Cost tracking | Langfuse stub (already in settings) | Enable with env var; no code change |
