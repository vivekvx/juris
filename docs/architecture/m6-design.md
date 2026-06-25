# M6 Enterprise Trust Layer — Architecture Design

**Date:** 2026-06-25
**Status:** DRAFT — awaiting human approval
**Scope:** AI Decision Ledger, Company Legal Memory, Policy Engine, the organization (tenant) boundary that makes all three possible, and the event/audit/trust models that bind them.
**Out of scope:** Implementation code, Pydantic models, API handlers, UI components. This is architecture only.
**Depends on:** M2 (documents, GCS storage, Firestore per-user scoping), M3 (chunking, embeddings, retrieval), M4 (conversations, messages, SSE chat, `ChunkCitation` provenance), M5 (voice codec around text).

---

## 0. Guiding Constraints

From the mission, treated as hard invariants:

| Constraint | How M6 honors it |
|------------|------------------|
| Extend existing architecture, don't replace | M6 adds an `org_id` dimension above the existing `owner_uid` scoping. No collection is renamed; no model is rewritten. The RAG/SSE pipeline keeps its shape and gains emission points. |
| Maintainability over cleverness | One storage engine (Firestore + GCS, already in use). One auth path (`get_current_user`). No Kafka, no new database, no event-sourcing framework. Append-only collections and an outbox pattern carry the "event architecture" without new infrastructure. |
| Enterprise scale | Per-org sharding of ledger/memory/audit subcollections. Each tenant's high-volume data is isolated under its own document tree, so no single collection becomes a global hotspot. |
| Auditability & explainability are first-class | Every AI answer already carries `ChunkCitation` provenance (M4). M6 promotes that from a UI nicety to a tamper-evident, hash-chained ledger entry that reconstructs *why* the system said what it said. |
| No implementation in this task | All structure is expressed as data-model tables and illustrative document shapes, never as code. |

**Central design decision — the tenant boundary.** Today Juris is single-tenant-per-user: every resource is scoped by `owner_uid`, and the 404-not-403 ownership rule (`conversations.py`) prevents cross-user enumeration. Enterprise trust requires the opposite of isolation in three specific places — *shared* memory, *org-wide* policy, *org-wide* audit visibility — while preserving per-user privacy everywhere else. M6 resolves this by introducing the **Organization** as the unit of trust, governance, and shared memory, and by making the existing single-user model a degenerate case: **org-of-one**. Every current user is migrated into a personal organization where they are the sole `OWNER`. Nothing about their experience changes; the scoping key simply widens from `owner_uid` to `(org_id, owner_uid)`.

---

## 1. Vision

Juris today answers a user's legal questions against that user's documents. That is an *assistant*. An enterprise legal operating system must additionally answer three institutional questions:

1. **"Why did the AI say that, and can we prove it later?"** — the **AI Decision Ledger**. Every AI decision is reconstructable, tamper-evident, and attributable to a model version, a prompt, a retrieval set, and a governing policy at a fixed point in time.
2. **"What does *our company* know and believe about *our* legal positions?"** — **Company Legal Memory**. Reusable institutional facts (entities, clauses, definitions, precedents, relationships) outlive any individual conversation or employee and are reused across the org.
3. **"What is the AI allowed to do here, and who approved it?"** — the **Policy Engine**. Governance rules constrain retrieval, generation, disclosure, and action, with explicit approval trails.

The product shift: from *a tool one lawyer uses* to *a system of record an institution trusts*. The trust comes not from the model being smarter, but from the system being **accountable** — every output is explained, governed, and provable.

---

## 2. Design Principles

1. **Provenance is not optional.** No assistant answer exists without a ledger entry that explains it. The ledger write is in the critical path, not a side effect.
2. **Append-only beats mutable.** Trust data (ledger, audit) is never updated or deleted in place. Corrections are new entries that supersede, preserving history.
3. **The pipeline emits; it does not branch.** M6 instruments the existing M4 RAG/SSE flow with emission points. It does not fork the pipeline into a "governed" and "ungoverned" path. There is one path; governance is woven in.
4. **Policy decides, the engine enforces, the ledger records.** These three responsibilities are separate. A policy is data. The engine evaluates it. The ledger records the evaluation. None of the three knows the others' internals.
5. **Shared by exception, private by default.** Conversations and personal drafts stay `owner_uid`-private. Only memory explicitly promoted to the org is shared. Visibility widens deliberately, never accidentally.
6. **One storage engine.** Firestore for structured + transactional data, GCS for blobs. No new datastore. Maintainability for a small team beats the throughput of a system nobody can operate.
7. **Reversible widening.** Every M6 addition is additive (new collections, new optional fields). The system runs unchanged if M6 features are disabled per-org via policy.
8. **Facts and decisions never mix.** Company Legal Memory holds **facts** — reusable organizational knowledge that may be revised. The AI Decision Ledger holds **decisions** — immutable history of what happened. A fact is reused; a decision is recorded once and never changes. They live in different collections and are never co-mingled, because mixing them would let mutable knowledge corrupt the historical record (and vice versa).

---

## 3. Scope

In scope for the M6 milestone:

- The **Organization** tenant boundary: orgs, membership, roles, the `(org_id, owner_uid)` scoping migration.
- **AI Decision Ledger**: append-only, hash-chained record of every AI decision (immutable history only), with full reconstruction inputs (model, prompt template version, retrieval set, policy snapshot, confidence) and **human overrides** as first-class immutable entries.
- **Company Legal Memory**: org-shared **facts only** — reusable knowledge entries (entities, clauses, definitions, precedents, relationships), their lifecycle (draft → reviewed → published → retired), and their injection into retrieval. No decision history.
- **Policy Engine**: declarative policy documents, an evaluation point in the chat pipeline, enforcement decisions (allow / warn / require-approval / deny / redact), and approval workflow state.
- **Event architecture**: synchronous append to trust collections plus an asynchronous **outbox** for fan-out (notifications, analytics, exports) without new infrastructure.
- **Trust model**: hash-chaining for tamper-evidence, provenance linkage from every answer to its ledger entry.
- **Audit model**: a second append-only stream for *access and administration* events (who read the ledger, who changed a policy, who published memory), distinct from the decision ledger.
- **Migration strategy** from the current per-user model.
- **The complete task breakdown** for implementing M6 (§18).

---

## 4. Non-Goals

Explicitly **not** in M6:

- **Not a new agent architecture.** The LLM path stays Gemini-via-`llm.py`. M6 governs and records the existing path; it does not add tool-use, multi-agent orchestration, or autonomous action.
- **Not a rules DSL or rules-engine product.** The Policy Engine evaluates a small, fixed, declarative schema — not a Turing-complete language. No embedded scripting.
- **Not real-time streaming infrastructure.** No Kafka, Pub/Sub-as-source-of-truth, or event-sourcing framework. The outbox is a Firestore collection drained by a worker.
- **Not blockchain.** Tamper-evidence is a hash chain stored in Firestore, optionally anchored. No distributed ledger, no consensus, no tokens.
- **Not SSO/SCIM/directory-sync in this milestone.** Org membership is managed in-app on top of existing Firebase auth. Enterprise IdP federation is future work (§16) and the model is built to accept it.
- **Not data-residency / regional sharding.** Single-region Firestore as today. The model leaves room for it (§16) but M6 does not implement it.
- **Not automated legal advice or action.** The Policy Engine can *block* and *flag*; it never *acts* on the user's behalf.

---

## 5. AI Decision Ledger

### 5.1 Purpose

The ledger answers: *for any AI output, what exactly produced it, under what governance, and has the record been altered since?* It is the spine of auditability and explainability.

### 5.2 What is a "decision"

A **decision** is one complete pass of the assistant producing an output: one user turn → one assistant answer. It is **not** one token and **not** one retrieval. Sub-steps (retrieval, policy evaluation, generation) are recorded as fields *within* the decision entry, not as separate ledger rows. This keeps the ledger at human-auditable granularity (one row = one answer a person can point at) while still capturing the full causal chain.

The ledger stores **decisions only** — immutable history: the question asked, the evidence seen, the reasoning metadata (model/prompt/policy), the answer produced, and any human actions taken on it. It never stores reusable knowledge; that is the role of Company Legal Memory (§6). This is the §2 fact/decision separation made concrete.

### 5.3 Reconstruction inputs

Each ledger entry captures everything needed to explain and, where deterministic, re-derive the answer:

| Field group | Captures | Why it matters for trust |
|-------------|----------|--------------------------|
| Identity | `org_id`, `actor_uid`, `conversation_id`, `message_id` | Who, where. Links the ledger row to the live message it explains. |
| Inputs | user query text, resolved `document_ids`, language | What was asked, against what scope. |
| Retrieval | ordered list of `ChunkCitation` (doc_id, chunk_index, page, score), retrieval params (`top_k`, `score_threshold`) | The exact evidence the model saw — already produced by `rag.retrieve`, now persisted. |
| Memory | IDs + versions of any Company Legal Memory entries injected | Which institutional knowledge shaped the answer. |
| Model | model name (`gemini-2.5-flash`), temperature, `max_output_tokens`, **prompt template version** | Reproducibility. A prompt change is a versioned event, not silent drift. |
| Policy | `policy_snapshot_id`, the evaluation outcome (allow/warn/redact/…), any redactions applied | Under what governance the answer was produced and released. |
| Output | assistant answer text (or content hash if stored elsewhere), `sources_used`, a confidence signal | What was said, how grounded. |
| Integrity | `sequence_no`, `prev_hash`, `entry_hash`, `created_at` | Tamper-evidence (§10). |

Human actions on a decision (overrides, annotations) are recorded as **separate, linked** ledger entries (§5.6, §5.7), never as edits to this entry. The decision entry above is written once and frozen.

### 5.4 Confidence signal

M6 does not invent a calibrated probability. It records **observable grounding signals** already available in the pipeline: number of citations above threshold, top citation score, whether `sources_used` was true, and whether the model emitted the "no relevant documents" disclaimer. These are stored verbatim and surfaced as an explainability aid — never as a guarantee. Honest signal beats a fabricated percentage.

### 5.5 Where it is written

Emission is woven into the existing `_stream` generator in `chat.py`. The pipeline already computes every input the ledger needs (history, `query_vec`, `citations`, `accumulated`, `asst_msg`). At the point it currently emits the `done` SSE event, it additionally **appends one ledger entry** within the same request, before `done` is sent. If the ledger write fails, the answer is still delivered (trust degrades to "answer without proof" only on infrastructure failure, and that failure is itself recorded in the audit stream). Policy may configure stricter behavior (§7: `require_ledger` denies release on ledger failure).

### 5.6 Immutability

Ledger entries are written once and never updated or deleted. A correction (e.g., a later determination that an answer was wrong) is a **new** entry of kind `annotation` that references the original `entry_hash`. A human changing an AI recommendation is a **new** entry of kind `override` (§5.7). The original `decision` remains in all cases. This is what makes the ledger admissible as a record rather than a cache. The three kinds — `decision`, `annotation`, `override` — are all immutable and hash-chained.

### 5.7 Human Override (first-class)

An **override** is the immutable record of a human changing, rejecting, or replacing an AI recommendation. It is a ledger entry of kind `override`, never an update to the decision it concerns — one entry per human action, hash-chained like every other ledger entry (§10), so override history is itself tamper-evident.

| Field | Captures |
|-------|----------|
| `decision_id` | the ledger entry whose recommendation was overridden |
| `approver` | uid of the human who overrode |
| `reason` | required justification (free text) |
| `timestamp` | `created_at`, UTC |
| `previous_recommendation` | the AI's original answer/outcome (hash + ref) |
| `final_outcome` | what the human substituted, plus disposition (`rejected` / `replaced` / `amended`) |

Because overrides are ordinary append-only ledger entries, future analytics answer **which** recommendations were overridden, **why**, **by whom**, and **how often** by querying kind=`override` over `(org_id, created_at)` — no separate store, no schema change. The approval workflow (§7.4 `require_approval`, §9) is one source of overrides: a reviewer rejecting or editing a held answer emits an override entry. A user correcting a delivered answer is another. Override is the *substantive* record (what changed about the AI outcome); the audit stream's access/admin view (§11) references it rather than duplicating it.

---

## 6. Company Legal Memory

### 6.1 Purpose

Institutional knowledge that is *true for the company* and should inform every relevant answer, independent of which employee asks or which conversation it surfaces in. Examples: "Our standard liability cap is 12 months' fees," a canonical clause library, an org-specific definition, a curated precedent a senior lawyer has blessed.

Memory stores **facts only** — reusable knowledge that may be revised over time. It never stores decision history; that lives in the AI Decision Ledger (§5). The two never mix (§2): a fact is reusable and versioned; a decision is immutable and recorded once. Promoting knowledge *out of* a past decision into Memory copies the reusable distillation; the decision itself stays in the ledger, untouched.

### 6.2 Memory entry kinds

| Kind | Content | Example |
|------|---------|---------|
| `entity` | A party, counterparty, subsidiary, or product the org refers to repeatedly | "Acme Corp = our largest reseller, MSA dated 2024-01" |
| `clause` | A canonical contract clause and its approved variants | Standard confidentiality clause, v3 |
| `definition` | An org-specific term of art | "Effective Date means…" |
| `precedent` | A reusable legal **principle distilled** from a reviewed prior answer (the distillation, not the decision record — the latter stays in the ledger §5) | "SaaS subscriptions attract GST at 18% — applies org-wide" |
| `relationship` | A durable connection between entities, clauses, or definitions | "Acme is a subsidiary of Globex; their 2025 NDA supersedes the 2023 LOI" |

These five kinds are exhaustive: Memory holds entities, clauses, definitions, precedents, and relationships — all **facts**. A settled stance the org takes is expressed as a `precedent` (distilled principle) or `definition`, not as decision history. Anything that is "what happened on a specific question" belongs in the ledger (§5), not here.

### 6.3 Lifecycle

Memory is not a free-for-all wiki; it is governed knowledge. Each entry moves through an explicit, append-tracked lifecycle:

```
draft ──submit──> in_review ──approve──> published ──retire──> retired
                       │
                       └──reject──> draft
```

Only `published` entries are eligible for injection into retrieval. `draft`/`in_review` entries are visible to authors/reviewers but never reach the model. Every transition is an audit event (§11) and names the actor. This is the institutional-memory analogue of the M4 citation discipline: knowledge that shapes answers must be attributable and reviewed.

### 6.4 How memory enters an answer

Memory reuses the existing retrieval substrate rather than inventing a parallel one. Published `entity`/`definition`/`precedent`/`relationship` entries carry an embedding (same `embedding.py` path as document chunks). At retrieval time, `rag.retrieve` is extended to query **two sources** — the user's document chunks (unchanged) and the org's published memory — merging by score. `clause` entries are retrieved by explicit reference rather than similarity (a clause is invoked, not stumbled upon). Injected memory entries are listed in the ledger (§5.3) and rendered as first-class citations in the answer, visually distinguished from document citations ("Company precedent [M2]" vs "Contract.pdf [1]").

**Why reuse retrieval instead of a separate "knowledge graph":** the embedding + cosine path is already built, tested, and operated. A graph store would be a new system to learn and run for marginal early benefit. The model leaves room to add structured relations later (§16) without migrating existing memory.

### 6.5 Scope and privacy

Memory is **org-scoped**, never global across tenants. A personal org (org-of-one) has a memory of one user — functionally identical to a private knowledge base. Promotion of a private conversation answer into shared memory is a deliberate, audited act requiring the `CONTRIBUTOR` role or higher; it never happens automatically.

---

## 7. Policy Engine

### 7.1 Purpose

Declarative governance over what the AI may retrieve, generate, disclose, and how outputs are released. The engine is the enforcement point; policies are data.

### 7.2 Policy shape (declarative, fixed schema — not a language)

A policy is a document with a small, enumerated set of conditions and effects. No scripting, no arbitrary expressions. Conceptually:

| Element | Values | Meaning |
|---------|--------|---------|
| `scope` | org-wide, role-specific, document-tag-specific | Where the policy applies |
| `trigger` | on-query, on-retrieval, on-generation, on-release | Which pipeline stage evaluates it |
| `condition` | matched document tags, detected topics (e.g. "litigation hold"), requesting role, presence of PII markers | What must be true to fire |
| `effect` | `allow`, `warn`, `redact`, `require_approval`, `deny`, `require_ledger` | What happens when it fires |
| `message` | human-readable rationale | Surfaced to the user and recorded in the ledger |

### 7.3 Evaluation point

The engine evaluates at four well-defined seams in the existing pipeline, all inside `_stream`:

```
user query
   │
   ├─ [on-query]     evaluate before embedding   ──> deny? short-circuit, record, inform user
   │
embed + retrieve
   │
   ├─ [on-retrieval] evaluate over retrieved set  ──> redact/drop restricted chunks
   │
build context + stream_response
   │
   ├─ [on-generation] system-prompt augmentation  ──> inject policy constraints into instruction
   │
accumulated answer
   │
   └─ [on-release]   evaluate before persisting    ──> require_approval? hold; redact? mask; allow? deliver
```

Each evaluation produces a **policy decision** recorded in the ledger entry for that turn. The default policy (and the only policy a personal org has) is a single `allow` — so the engine is a no-op for existing single-user behavior until an admin authors stricter policy. This is how M6 stays backward-compatible: governance is opt-in per org.

### 7.4 Effects in detail

- **`allow`** — pass through (default).
- **`warn`** — deliver, but attach a visible advisory and record it.
- **`redact`** — mask matched content (e.g., a restricted clause) before release; the redaction is itself ledgered.
- **`require_approval`** — the answer is generated but **held**; a reviewer with sufficient role must release it. Held state lives in the approval workflow (§12 boundaries, modeled in Firestore §8).
- **`deny`** — refuse; the user sees the policy `message`; the refusal is ledgered (a denied decision is still a decision).
- **`require_ledger`** — release only if the ledger entry was durably written; trades availability for provability where regulation demands it.

### 7.5 What the engine never does

It does not call out to the model to "decide" policy (that would be ungovernable). Conditions are matched against structured signals (tags, roles, detected-topic flags, PII markers from a deterministic scan). Topic/PII detection may *use* a model to produce a signal, but the **decision** is a deterministic match against that signal, so it is reproducible and auditable.

---

## 8. Firestore Data Model

### 8.1 Principle

Additive only. Existing collections (`conversations`, `documents`, `users`, chunk storage) are unchanged except for new **optional** fields (`org_id`) that default such that an unmigrated read still works. All new trust data lives under the org document tree, sharding naturally by tenant.

### 8.2 Collection layout

```
organizations/{org_id}
  ├─ (org document: name, plan, created_at, settings, default_policy_id)
  ├─ members/{uid}             role, status, invited_by, joined_at
  ├─ policies/{policy_id}      declarative policy (versioned; see 8.4)
  ├─ policy_snapshots/{snap_id}   immutable point-in-time bundle of active policies
  ├─ memory/{entry_id}         Company Legal Memory entry + lifecycle state + embedding
  ├─ ledger/{entry_id}         AI Decision Ledger — append-only, hash-chained
  ├─ audit/{event_id}          access/admin audit — append-only
  ├─ approvals/{approval_id}   held answers awaiting release (Policy require_approval)
  └─ outbox/{event_id}         async fan-out queue (drained by worker; see §9)

conversations/{conv_id}        + org_id  (new optional field)
documents/{doc_id}             + org_id  (new optional field)
users/{uid}                    + default_org_id, org_memberships[]  (new optional fields)
```

### 8.3 Ledger entry — illustrative document shape

(Data model, not code. Field names follow existing conventions: snake_case, UTC ISO-8601 with `Z`.)

```
organizations/{org_id}/ledger/{entry_id}
{
  "id":               "<entry_id>",
  "org_id":           "<org_id>",
  "kind":             "decision",            // decision | annotation
  "sequence_no":      10427,                 // monotonic per org
  "actor_uid":        "<uid>",
  "conversation_id":  "<conv_id>",
  "message_id":       "<assistant message id>",
  "query":            "Can we cap liability at 6 months?",
  "document_ids":     ["<doc_id>", "..."],
  "retrieval": {
    "top_k": 5, "score_threshold": 0.3,
    "citations": [ { "doc_id": "<doc_id>", "chunk_index": 4,
                     "page_number": 12, "score": 0.71,
                     "original_filename": "MSA.pdf" } ]
  },
  "memory_used":      [ { "entry_id": "<entry_id>", "version": 3, "kind": "precedent" } ],
  "model": {
    "name": "gemini-2.5-flash", "temperature": 0.3,
    "max_output_tokens": 2048, "prompt_template_version": "m6.1"
  },
  "policy": {
    "snapshot_id": "<snap_id>",
    "evaluations": [
      { "trigger": "on-release", "effect": "allow", "policy_id": "<policy_id>" }
    ]
  },
  "output": {
    "answer_hash": "sha256:<hex>", "answer_ref": "<message_id>",
    "sources_used": true,
    "grounding": { "citations_above_threshold": 3, "top_score": 0.71,
                   "disclaimer_emitted": false }
  },
  "prev_hash":  "sha256:<hex of entry sequence_no-1>",
  "entry_hash": "sha256:<hex over canonical serialization of this entry>",
  "created_at": "2026-06-25T06:30:00Z"
}
```

### 8.4 Policy & snapshot

`policies/{policy_id}` holds the editable, versioned policy. Because a ledger entry must reference *the exact governance in force at decision time*, the engine reads from an immutable **`policy_snapshots/{snap_id}`** — a frozen bundle of all active policies, created whenever any policy changes. The ledger stores the `snapshot_id`, so a later policy edit can never retroactively alter what governed a past decision. This mirrors the `ChunkCitation` discipline: capture the evidence as it was, not as it is now.

### 8.5 Memory entry — illustrative shape

```
organizations/{org_id}/memory/{entry_id}
{
  "id": "<entry_id>", "org_id": "<org_id>", "kind": "precedent",
  "title": "Liability cap principle",
  "body":  "Org standard: liability caps below 12 months' fees are not accepted.",
  "tags":  ["liability", "negotiation"],
  "lifecycle": "published",          // draft|in_review|published|retired
  "version": 3,
  "embedding_ref": "<vector handle>",   // same path as chunk embeddings
  "author_uid": "<uid>", "reviewed_by": "<uid>", "published_at": "2026-06-20T10:00:00Z",
  "supersedes": "<prior entry_id or null>",
  "created_at": "2026-06-19T09:00:00Z", "updated_at": "2026-06-20T10:00:00Z"
}
```

### 8.6 Indexing & scale notes

- Ledger and audit are queried by `(org_id, sequence_no)` and `(org_id, created_at)` — composite indexes per org. Per-org sharding keeps any single org's write rate well within Firestore limits; no global hot collection exists.
- Memory similarity search follows the existing in-process cosine approach (`chunk_repo.cosine_top_k`) over the org's published set. If an org's memory outgrows in-process scan, the §16 upgrade path swaps in a vector index without changing the entry shape.
- `sequence_no` monotonicity per org is maintained by a transactional counter on the org document — the same Firestore transaction that appends the entry, so the chain cannot fork.

---

## 9. Event Architecture

### 9.1 Two tiers: critical-path append, async fan-out

M6 needs events without a streaming platform. The split:

- **Tier 1 — synchronous append (trust-critical).** Ledger and audit writes happen *inside the request*, in a Firestore transaction, before the user is told the action succeeded. These are not "events" in a queue sense; they are durable records the system's correctness depends on.
- **Tier 2 — asynchronous outbox (everything else).** Notifications ("an answer needs your approval"), analytics rollups, export jobs, and external webhooks must not block or endanger the critical path. The Tier-1 transaction *also* writes a row to `organizations/{org_id}/outbox/{event_id}`. A background worker drains the outbox and performs side effects, marking rows done.

```
request ──┐
          ▼
  Firestore transaction:
    append ledger entry  ─┐
    append audit event    ├─ atomic
    enqueue outbox row   ─┘
          ▼
  respond to user  (trust record already durable)

  ── later, out of band ──
  outbox worker ─> notify / analytics / export / webhook ─> mark done
```

### 9.2 Why the outbox pattern specifically

It gives exactly-once-effect semantics on top of Firestore without a message broker: the event is committed atomically with the state change it describes, so there is no "wrote the ledger but lost the notification" gap and no dual-write inconsistency. The worker is idempotent (keyed by `event_id`), so retries are safe. This is the maintainability-over-cleverness choice — an engineer can read the outbox collection and see exactly what is pending.

### 9.3 Reuse of existing background-task discipline

`chat.py` already runs fire-and-forget tasks with strong references (`_background_tasks`) for title generation. The outbox worker generalizes that pattern from in-process tasks to a durable queue — the same idea, made crash-safe.

---

## 10. Trust Model

### 10.1 Threats addressed

| Threat | Control |
|--------|---------|
| Silent post-hoc alteration of a decision record | Hash chain: each entry stores `prev_hash`; altering entry N invalidates every entry > N. Verifiable by re-walking the chain. |
| Retroactive policy rewriting to justify a past answer | Immutable `policy_snapshots`; ledger references the snapshot in force at decision time. |
| Deletion of an inconvenient entry | Append-only collections; deletes blocked by security rules; a gap in `sequence_no` is itself evidence. |
| Prompt/model drift hiding *why* answers changed | Versioned `prompt_template_version` and recorded model params per entry. |
| Disputed "what did the AI actually say" | `answer_hash` over the delivered text; the message and ledger cross-reference. |

### 10.2 Hash chaining

Within an org, entries form a chain: `entry_hash = sha256(canonical(entry_without_hash) ‖ prev_hash)`. The org document stores the latest `head_hash`. Verification re-walks from genesis (or any anchored checkpoint) and recomputes. Cost is linear and runs as a background audit job, not per-request.

### 10.3 Optional anchoring (configurable, not required)

For tenants needing third-party-verifiable integrity, the periodic `head_hash` can be anchored to an external append-only store (e.g., a timestamping authority or a write-once GCS bucket with object retention lock). M6 designs the seam; enabling it is a per-org setting. No blockchain.

### 10.4 What trust does *not* mean here

The ledger proves *what the system did and that the record is intact*. It does **not** prove the answer was legally correct. Explainability ≠ authority. The system's own system prompt already flags when a licensed attorney is required; the trust layer records that flag, it does not substitute for it.

---

## 11. Audit Model

### 11.1 Two distinct streams — and why

The **decision ledger** (§5) records what the *AI* did. The **audit stream** records what *humans and admins* did to the trust system itself:

| Audit event | Example |
|-------------|---------|
| Access | "User X read the ledger for conversation Y." |
| Policy change | "Admin Z edited policy P; snapshot S created." |
| Memory governance | "Reviewer R published memory entry M v3." |
| Membership | "Owner invited user U as CONTRIBUTOR." |
| Release / override | "Approver A released (or overrode) held answer for message M." References the `override` ledger entry (§5.7); does not duplicate its content. |
| Integrity | "Chain verification run completed; head matches." / "Ledger write failed for message M." |

Keeping them separate matters: a compliance reviewer querying "every AI decision touching litigation-hold documents" must not wade through "who looked at what," and a security reviewer asking "who changed governance" must not parse AI decisions. Same storage mechanics (append-only, per-org, outbox-fanned), different stream, different access controls.

### 11.2 Access to audit data is itself audited

Reading the ledger or audit stream emits an audit event. This is recursive by design and terminates naturally: the read-of-a-read is a normal append, not a special case.

---

## 12. API Boundaries

Design of boundaries only — no handlers, no routes implemented in M6 Task 1. The shape mirrors existing routers (`/api/...`, `get_current_user`, service layer does Firestore, API layer does HTTP).

| Boundary | Responsibility | Auth/role |
|----------|----------------|-----------|
| Organization & membership | Create org, invite/remove members, assign roles | `OWNER`/`ADMIN` |
| Policy administration | CRUD policies (creates snapshots), read effective policy | `ADMIN` |
| Memory governance | Submit/review/publish/retire memory entries | `CONTRIBUTOR`+ to author, `REVIEWER`+ to publish |
| Ledger read | Query/inspect decision entries; verify chain | `AUDITOR`+ (read-only) |
| Audit read | Query access/admin events | `AUDITOR`+ (read-only) |
| Approvals | List held answers, release/reject | `REVIEWER`+ |
| Chat (existing, extended) | Unchanged contract; now emits ledger + evaluates policy internally | member of org |

**The chat endpoint contract does not change.** `POST /api/conversations/{id}/messages` keeps its request body and SSE protocol (`token | citations | done | error`). M6 adds *internal* emission and *internal* policy evaluation. A new SSE event `policy` may be **added** (additive, ignorable by old clients) to surface warnings/denials/redactions in real time — existing clients that ignore unknown events keep working, exactly as M5's auto-play tolerance for unknown events showed.

### 12.1 Service-layer boundaries

New services parallel to existing ones (`conversations.py`, `documents.py`):

- `organizations` service — org/membership Firestore ops, role checks.
- `ledger` service — transactional append + chain maintenance + verification.
- `memory` service — lifecycle transitions + embedding + retrieval extension.
- `policy` service — policy CRUD, snapshot creation, evaluation given a context.
- `audit` service — append + query.
- `outbox` worker — drain + idempotent side effects.

Each obeys the existing rule: **services touch Firestore/GCS only, no HTTP concerns**, ownership/role checks return 404 for cross-org access (no tenant enumeration), consistent with the M4 404-not-403 convention widened from user to org.

---

## 13. UI Concepts

Concepts only — no components built in M6 Task 1.

1. **"Why this answer" panel.** On any assistant message, expand to see its ledger entry: the documents and memory used (already partly shown as citations in M4), the model + prompt version, the governing policy decision, and the grounding signal. This turns the existing citation cards into a full explainability surface.
2. **Trust badge on messages.** A small, honest indicator: grounded-in-sources / general-knowledge / policy-flagged / held-for-approval. Derived from ledger fields, never decorative.
3. **Memory workbench.** Author and review Company Legal Memory: a queue of `in_review` entries, diff between versions, publish/retire actions. Mirrors the document-management UI rhythm from M2.
4. **Policy console.** Admin view of policies, what each does in plain language, and a "test against a past query" sandbox that replays a ledger entry through current policy to preview effect.
5. **Audit explorer.** Filterable timeline over decision ledger and audit streams, with chain-verification status. Read-only for `AUDITOR`.
6. **Approval inbox.** Held answers awaiting release, with the generated text, its citations, and the firing policy's rationale.

All six read from M6 data; none require changing the existing conversation UI beyond the additive "Why this answer" expansion on `message-bubble`.

---

## 14. Security Considerations

| Concern | Control |
|---------|---------|
| **Cross-tenant leakage** | Every trust collection is nested under `organizations/{org_id}`. Firestore security rules and service-layer role checks gate on membership in that org. Cross-org reads return 404, never 403 (no tenant enumeration), extending the existing convention. |
| **Privilege escalation** | Roles are least-privilege and additive: `MEMBER` < `CONTRIBUTOR` < `REVIEWER` < `AUDITOR` < `ADMIN` < `OWNER`. Auditor is read-only by construction — it can inspect everything and change nothing, which is what compliance requires. Role changes are audit events. |
| **Tamper with the record** | Append-only enforced at the security-rule layer (no update/delete on `ledger`/`audit`). Hash chain detects any out-of-band store mutation. |
| **Memory poisoning** | Only `published` memory reaches the model, and publishing requires `REVIEWER`+. A malicious `MEMBER` can draft but cannot influence answers. Every publish is attributable. |
| **Policy used as exfiltration** | Policy conditions match structured signals only; they cannot read arbitrary data or call out. `redact`/`deny` reduce disclosure; no effect *increases* a user's access. |
| **PII in the ledger itself** | The ledger necessarily contains query and answer text. It inherits per-org scoping and the same Firestore protections as conversations. Where regulation forbids storing answer text, policy can store only `answer_hash` + a reference, keeping provenance without the content. |
| **Audit-log access abuse** | Reading audit/ledger is role-gated and itself audited (§11.2). |
| **Outbox as a side channel** | Outbox rows carry references (IDs), not secrets. Workers re-fetch data under the same access rules; the outbox does not bypass authorization. |
| **Prompt-injection via documents/memory** | Unchanged from M4's exposure plus a new mitigation: the on-generation policy seam can inject constraints, and memory passes through the same review gate, so injected content in *shared* knowledge is human-reviewed before it can affect others. |

---

## 15. Migration Strategy

The migration is from "per-user, no org" to "per-org, org-of-one by default." It must be zero-downtime and reversible.

### 15.1 Phases

1. **Additive deploy (no behavior change).** Ship the new collections and the optional `org_id` fields. Nothing reads them yet. Existing reads/writes are untouched. Risk: nil.
2. **Backfill personal orgs.** For each existing user, create `organizations/{personal_org_id}` with that user as `OWNER`, a default `allow` policy, and a single empty memory set. Idempotent, batched (reuse the batch pattern from `delete_conversation`). Stamp existing `conversations` and `documents` with `org_id = personal_org_id`. Users with no `org_id` are treated as their personal org at read time, so the backfill can run lazily and incrementally.
3. **Dual-read compatibility window.** Services resolve scope as `org_id ?? personal_org_of(owner_uid)`. Code paths work whether or not a record has been stamped. This is the reversibility guarantee: rolling back the feature flag returns to pure `owner_uid` behavior because `org_id` is additive.
4. **Enable trust emission per org.** Turn on ledger writes and policy evaluation behind a per-org setting, defaulting **on** for new enterprise orgs and **off** (no-op `allow`, optional ledger) for personal orgs to avoid imposing overhead on individuals. Flip personal orgs on only if the user opts in.
5. **Enforce.** Once an org has authored real policies and verified its ledger chain, `require_ledger`/`require_approval` effects can be enabled. This is an org-admin decision, not a global flip.

### 15.2 Data backfill safety

- Backfill is read-mostly + idempotent writes keyed by deterministic `personal_org_id = f(uid)`; re-running is safe.
- No existing document is *deleted or rewritten destructively* — only an optional field is added.
- A migration audit event is emitted per org created, so the migration itself is on the record.

---

## 16. Future Compatibility

M6's seams are chosen so later milestones extend without breaking the schema.

| Future capability | Path from M6 |
|-------------------|--------------|
| Enterprise SSO / SCIM | `members` already models role + status + invited_by. Federate identity by mapping IdP subjects to `uid`; membership model is unchanged. |
| Structured legal knowledge graph | `memory` entries carry `kind` + `tags` today; add typed relations between entries as a new optional field. Existing similarity injection keeps working. |
| Vector index for memory at scale | `embedding_ref` is an opaque handle. Swap in-process cosine for a managed vector index without changing entry shape. |
| Streaming/real-time audit feeds | Outbox already decouples fan-out; point a worker at a streaming sink. Source of truth stays Firestore. |
| Third-party integrity attestation | `head_hash` anchoring seam (§10.3) is designed; enabling it is config. |
| Data residency / regional tenants | Orgs are the shard unit; a future `region` on the org document can route to a regional Firestore without touching the model. |
| Policy-as-code import/export | Policies are declarative documents; serialize to/from a file format without engine changes. |
| Cross-org benchmarking (opt-in) | Ledger grounding signals are structured; aggregate anonymized metrics without exposing content. |

No M6 decision needs revision for any of the above — the same forward-compatibility property M4 held toward M5 and M5 toward M6.

---

## 17. Risks

| Risk | Likelihood | Impact | Mitigation |
|------|-----------|--------|------------|
| **Ledger write in critical path adds latency** | Med | Med | One transactional append per *turn* (not per token); Firestore single-doc write is sub-50ms. Stricter `require_ledger` is opt-in, so the cost is paid only where provability is mandated. |
| **Scope-resolution bugs leak data across orgs** | Low | Critical | Single choke-point scope resolver (`org_id ?? personal_org_of(uid)`) used by every service; cross-org returns 404; covered by the existing ownership-test discipline (M4.5 added explicit 404-for-wrong-owner tests — extend to wrong-org). |
| **Hash chain corruption halts auditing** | Low | High | Chain is verified out-of-band, not per-request; a break is detected and reported (audit event), not fatal to live serving. Checkpoints bound re-walk cost. |
| **Policy engine becomes a de-facto programming language** | Med | High | Hard architectural ban (§4): fixed enumerated schema, no expressions. Resist feature requests that smuggle in scripting; add a new enumerated condition instead. |
| **Memory review queue becomes a bottleneck** | Med | Low | Publishing is async and role-delegable; personal orgs bypass review (author = reviewer). Drafts never block answers. |
| **Outbox worker falls behind** | Low | Med | Idempotent, horizontally runnable; lag affects only notifications/analytics, never the trust record (Tier-1 is synchronous). |
| **Storing answer text raises data-retention liability** | Med | Med | Policy can switch a ledger to `answer_hash`-only (§14), preserving provenance without content. Per-org configurable. |
| **Migration backfill errors on large tenants** | Low | Med | Lazy + idempotent + batched; lazy read-time resolution means backfill correctness is a performance optimization, not a correctness dependency. |

---

## 18. Complete M6 Task Breakdown

Sequenced so each task ships green (tests, lint, types) and the system is usable after each. Mirrors the M5 cadence: architecture first, then thin vertical slices.

| Task | Title | Deliverable | Depends on |
|------|-------|-------------|------------|
| **M6.1** | **Architecture (this document)** | `docs/architecture/m6-design.md`. No code. | — |
| **M6.2** | **Organization foundation** | `Organization`, `Membership` models; `organizations` service (create org, membership, role checks); the single scope-resolver (`org_id ?? personal_org_of(uid)`). Backend only. Tests: role gating, cross-org 404, scope resolution. | M6.1 |
| **M6.3** | **Org-of-one migration** | Backfill job creating personal orgs; optional `org_id` on `conversations`/`documents`/`users`; dual-read compatibility. Tests: idempotent backfill, lazy resolution, rollback safety. | M6.2 |
| **M6.4** | **Audit stream + outbox** | `audit` service (append/query, append-only rules); `outbox` collection + idempotent worker; reusable transactional-append helper. Tests: atomic append+enqueue, idempotent drain, append-only enforcement. | M6.2 |
| **M6.5** | **AI Decision Ledger core** | `ledger` service: transactional append with per-org `sequence_no`, hash chaining, chain verification job. No pipeline wiring yet. Tests: chain integrity, tamper detection, sequence monotonicity. | M6.4 |
| **M6.6** | **Ledger emission in chat** | Wire one ledger append into `_stream` at the `done` seam, capturing retrieval/model/grounding inputs already present. Additive; chat contract unchanged. Tests: every answered turn produces exactly one entry; failure path records to audit. | M6.5 |
| **M6.7** | **Policy Engine core** | `policy` service: declarative schema, snapshot creation, `evaluate(context) -> decision`. Default `allow`. No pipeline wiring. Tests: each effect, snapshot immutability, no-op for personal orgs. | M6.2 |
| **M6.8** | **Policy enforcement in chat** | Wire the four evaluation seams (on-query/retrieval/generation/release) into `_stream`; add additive `policy` SSE event; record decisions in the ledger. Tests: deny short-circuits, redact masks, require_approval holds, allow is transparent. | M6.6, M6.7 |
| **M6.9** | **Approval workflow** | `approvals` collection + service; held-answer release/reject; outbox notification on hold. Tests: hold→release delivers, reject discards, role gating. | M6.8 |
| **M6.10** | **Company Legal Memory core** | `memory` service: entry kinds, lifecycle state machine, embedding on publish, supersede chain. Tests: lifecycle transitions, only-published-is-eligible, attribution. | M6.4 |
| **M6.11** | **Memory injection into retrieval** | Extend `rag.retrieve` to merge org published memory with document chunks; memory citations distinguished; recorded in ledger. Tests: merge ordering, memory appears in ledger, personal-org parity. | M6.10, M6.6 |
| **M6.12** | **Trust & audit read APIs** | Read-only boundaries for ledger query, chain-verify, audit query; `AUDITOR` role. Tests: read gating, read-emits-audit, cross-org 404. | M6.5, M6.4 |
| **M6.13** | **"Why this answer" UI** | Frontend: expand a message to its ledger entry (sources, model/prompt version, policy decision, grounding); trust badge. Additive to `message-bubble`. Tests: renders from ledger, badge states, graceful absence. | M6.6 |
| **M6.14** | **Memory workbench UI** | Frontend: author/review/publish/retire memory; review queue; version diff. Tests: lifecycle actions, role gating in UI. | M6.10 |
| **M6.15** | **Policy console + approval inbox UI** | Frontend: policy admin in plain language, replay-against-past-query sandbox, held-answer inbox. Tests: policy CRUD flows, release/reject flows. | M6.8, M6.9 |
| **M6.16** | **Audit explorer UI + hardening** | Frontend: filterable ledger/audit timeline with chain-verification status. Plus cross-cutting hardening: load-test per-org ledger throughput, security-rule review, migration dry-run on a copy. Tests: explorer filters, verification surfacing, perf budgets. | M6.12 |

**Sequencing logic:** foundation (M6.2–M6.4) before the three pillars; each pillar lands backend-core then pipeline-wiring then UI; trust emission (M6.6) precedes everything that reads the ledger; policy enforcement (M6.8) precedes approvals (M6.9). After **M6.6** the system already produces an audit trail for every answer — value lands early. After **M6.8** it is governed. After **M6.11** it has institutional memory. The UI tasks (M6.13–M6.16) make each capability visible but are not prerequisites for the trust guarantees, which hold at the data layer.

---

## 19. Summary of Decisions

| Area | Decision | Reason |
|------|----------|--------|
| Tenant boundary | Introduce `Organization`; make today's single-user the org-of-one case | Shared memory/policy/audit need a unit above the user; degenerate case preserves current UX |
| Scoping | Widen `owner_uid` → `(org_id, owner_uid)` via one resolver; cross-org returns 404 | Extends, not replaces; reuses the M4 no-enumeration convention |
| Decision granularity | One ledger entry per answered turn; sub-steps are fields | Human-auditable rows; full causal chain without row explosion |
| Ledger placement | Synchronous append inside `_stream` at the `done` seam | Provenance is critical-path, not a side effect |
| Immutability | Append-only + hash chain + immutable policy snapshots | Tamper-evidence; admissible record, not a cache |
| Fact/decision separation | Memory = reusable facts (5 kinds); Ledger = immutable decisions; never co-mingled | Mutable knowledge can't corrupt history; history stays admissible |
| Human override | First-class immutable ledger entry (kind=`override`) capturing decision_id, approver, reason, timestamp, prior recommendation, final outcome | Overrides are analyzable history, not silent edits; analytics need no new store |
| Memory | Reuse embedding/retrieval; governed lifecycle; published-only injection; **facts only** | One retrieval substrate; reviewed knowledge only shapes answers |
| Policy engine | Fixed declarative schema, deterministic match, four pipeline seams | Governable and reproducible; never a scripting language |
| Event architecture | Tier-1 transactional append + Tier-2 Firestore outbox | Events without a broker; atomic, idempotent, operable |
| Trust | Per-org hash chain, optional external anchoring, no blockchain | Verifiable integrity at Firestore cost |
| Audit | Separate stream for human/admin actions; reads are audited | Compliance and security queries stay clean |
| Storage | Firestore + GCS only; additive collections under the org tree | Maintainability; per-org sharding for scale |
| Chat contract | Unchanged; additive `policy` SSE event only | Backward compatibility, as M5 demonstrated with unknown-event tolerance |
| Migration | Additive deploy → lazy idempotent backfill → dual-read → opt-in enforce | Zero-downtime, reversible |
| Rollout of trust | On for enterprise orgs, opt-in for personal | Don't tax individuals with enterprise overhead |
