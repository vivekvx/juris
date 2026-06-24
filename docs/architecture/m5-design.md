# M5 Voice Conversations — Architecture Design

**Date:** 2026-06-24
**Status:** DRAFT — awaiting human approval
**Scope:** Voice input (speech → transcript), voice output (assistant text → speech), voice composer UX, voice settings, provider integration
**Out of scope:** Real-time/duplex streaming voice (Gemini Live), telephony, voice cloning, on-device STT, new agent architecture, memory system, vector DB migration
**Depends on:** M4 — `POST /api/conversations/{id}/messages` SSE endpoint, `Message` model, `Conversation` model, RAG pipeline (`embed_query` → `cosine_top_k` → `stream_response`)

---

## 0. Guiding Constraints

From the task, treated as hard invariants:

| Constraint | How M5 honors it |
|------------|------------------|
| Reuse existing conversation system | Voice produces/consumes the same `Message` documents. No new conversation type. |
| Reuse existing chat endpoint where possible | The chat SSE endpoint is **untouched**. Voice wraps it: STT feeds `content`, TTS reads the response. |
| No new agent architecture | Voice is pure transport (audio ⇄ text). The RAG/LLM path is identical to M4. |
| No memory system | No persisted voice state beyond optional audio blobs. No cross-conversation recall. |
| No vector DB migration | Retrieval is unchanged. Transcript text flows into the existing `embed_query` path. |

**Central design decision:** Voice is a **codec around text**, not a parallel pipeline. The transcript is the unit that enters the system; speech audio never reaches the LLM or the retriever.

**Why transcribe-first is mandatory (not just convenient):** M4 RAG embeds the *query string* (`embed_query(content)`) to retrieve chunks. There is no embedding path for raw audio. Therefore the transcript must exist before the chat call. This turns out to be the cleanest reuse story — the existing `POST /{id}/messages` accepts `content: str` unchanged, and the transcript is just another source of that string.

---

## 1. Voice Architecture

```
┌─────────────────────────── Client (browser / mobile web) ───────────────────────────┐
│                                                                                       │
│  [🎙 Mic] ── MediaRecorder ──> audio blob (webm/opus | mp4/aac)                       │
│      │                                                                                 │
│      │ 1. POST /api/voice/transcribe  (multipart audio)                               │
│      ▼                                                                                 │
│  transcript text ──> [editable preview] ──> user confirms / edits                     │
│      │                                                                                 │
│      │ 2. POST /api/conversations/{id}/messages   ← EXISTING M4 ENDPOINT, UNCHANGED    │
│      ▼                                                                                 │
│  SSE token stream ──> rendered assistant message (+ citations)                         │
│      │                                                                                 │
│      │ 3. POST /api/voice/synthesize  { text }   (after `done` event)                  │
│      ▼                                                                                 │
│  audio/mpeg ──> <audio> playback (autoplay if gesture-permitted)                       │
│                                                                                        │
└────────────────────────────────────────────────────────────────────────────────────┘
                          │                    │                     │
                  ┌───────▼──────┐    ┌────────▼────────┐   ┌────────▼────────┐
                  │ /voice/      │    │ /conversations/ │   │ /voice/         │
                  │  transcribe  │    │  {id}/messages  │   │  synthesize     │
                  │ (NEW, M5)    │    │ (M4, REUSED)    │   │ (NEW, M5)       │
                  └───────┬──────┘    └────────┬────────┘   └────────┬────────┘
                          │                    │                     │
                  Cloud Speech-to-Text   RAG + Gemini stream   Cloud Text-to-Speech
```

**Three discrete steps, two new stateless endpoints.** The chat step in the middle is identical to M4 — same request body, same SSE protocol, same persistence, same citations.

**Why three steps and not one combined `/voice/chat`?**

1. **Transcript review is a correctness feature.** STT errors are common with legal terminology, names, and accented speech. Showing the editable transcript before sending lets the user correct "indemnification" misheard as "in deformation" *before* it pollutes retrieval and the answer. Critical for a legal product.
2. **Reuse.** Folding STT into the chat endpoint would fork it. Keeping them separate means the chat endpoint stays byte-for-byte the M4 implementation.
3. **TTS is independent of chat.** Synthesis runs on the *completed* assistant text after the `done` event, so it cannot be part of the streaming request anyway.

**Auto-send mode** (a UX toggle, §6) skips the manual confirm tap but still runs the same three calls in sequence — it does not merge endpoints.

---

## 2. Audio Upload Flow

### Recording (client)

- `navigator.mediaDevices.getUserMedia({ audio: true })` → `MediaRecorder`.
- **Format is platform-dependent and the backend must accept all of them:**
  - Chrome / Android: `audio/webm;codecs=opus`
  - Firefox: `audio/ogg;codecs=opus`
  - iOS / macOS Safari: `audio/mp4` (AAC)
- Single push-to-talk segment per turn. `MediaRecorder.stop()` → one `Blob`.

### Limits (enforced client and server)

| Limit | Value | Reason |
|-------|-------|--------|
| Max duration | 120 s | Caps STT cost; legal questions are short. UI shows a countdown. |
| Max upload size | 10 MB | DoS guard. 120 s Opus ≈ 1 MB; 10 MB is generous headroom for AAC. |
| Min duration | 0.4 s | Reject accidental taps before an STT call is spent. |
| Accepted MIME | `audio/webm`, `audio/ogg`, `audio/mp4`, `audio/wav`, `audio/mpeg` | Cover all browser outputs. |

### Upload

```
POST /api/voice/transcribe
  Content-Type: multipart/form-data
  Body: file=<audio blob>, language?=<BCP-47 hint, optional>
  Returns: 200 { "text": str, "language": str, "duration_ms": int, "confidence": float }
```

The audio is read into memory, sent to STT, and **discarded** — not persisted by default (see §7, §8). Cloud Run's in-request memory holds at most one 10 MB blob per concurrent request.

---

## 3. STT Provider Choice

**Decision: Google Cloud Speech-to-Text v2 (primary).**

The deciding factor is **audio format**. Browsers emit `webm/opus` (Chrome/Android) and `mp4/aac` (Safari). Cloud STT v2 ingests `WEBM_OPUS` and `OGG_OPUS` natively and auto-detects others — **no server-side transcode**. Avoiding `ffmpeg` keeps Cloud Run CPU-light and adds no native binary to the image.

| Provider | Browser-format ingest | Indian-language quality | New dep | Auth | Verdict |
|----------|----------------------|-------------------------|---------|------|---------|
| **Cloud Speech-to-Text v2** | ✅ webm/opus, ogg/opus direct | ✅ dedicated `latest_long` + chirp_2 models, strong hi/ta/te/kn | `google-cloud-speech` | reuses existing service account | **Chosen** |
| Gemini 2.5 Flash native audio | ⚠️ accepts wav/mp3/ogg/flac/aac — **not webm container** → needs client mp3 encode or server transcode | ✅ proven multilingual (M4) | none (reuses `google-genai`) | existing API key | Alternative; see below |
| OpenAI Whisper API | ✅ webm | ✅ good | new vendor, new key | new credential | Rejected — adds a vendor outside the Google trust boundary |

**Why not Gemini native transcription, given we already have the client?** It is genuinely attractive (zero new dependency, rung-4 reuse). The blocker is the `webm` container: Gemini's documented audio inputs are WAV/MP3/AIFF/AAC/OGG-Vorbis/FLAC, and Chrome's dominant `audio/webm;codecs=opus` is not on that list. Supporting it would require either client-side MP3 encoding (`lamejs`, extra bundle weight + CPU) or server-side `ffmpeg` transcode (native dep on Cloud Run). Cloud STT eats the browser blob as-is, so it wins on integration friction despite being a new SDK.

**Documented upgrade/alt paths (no schema change required):**
- If single-vendor consolidation becomes a priority, switch the `transcribe` service body to Gemini once we add client-side encoding — the endpoint contract is unchanged.
- Cloud STT v2 **streaming** recognition is the natural M6 path for live partial transcripts (§13).

**Language handling:** Pass the user's preferred language (from voice settings, §6) as a recognition hint when set; otherwise rely on Cloud STT auto-detection across the configured language set. The transcript then flows into the existing chat path, where Gemini already "responds in the same language" (M4 system prompt) — no new language logic.

**Config additions (`Settings`):**
```python
stt_provider: str = "google_cloud"          # google_cloud | gemini
stt_model: str = "latest_long"              # Cloud STT v2 recognizer model
voice_max_audio_seconds: int = 120
voice_max_audio_bytes: int = 10 * 1024 * 1024
```

---

## 4. TTS Provider Choice

**Decision: Google Cloud Text-to-Speech (primary backend), with Web Speech API `SpeechSynthesis` as a zero-cost client fallback.**

| Provider | Quality | Indian languages | Cost | Where it runs | Verdict |
|----------|---------|------------------|------|---------------|---------|
| **Cloud Text-to-Speech (Neural2 / Chirp3-HD)** | High, SSML, consistent | ✅ hi, ta, te, kn, bn, mr | ~$16/1M chars (Neural2) | backend | **Chosen (primary)** |
| Web Speech API `SpeechSynthesis` | Variable per device | Patchy on some OSes | $0 | client | **Fallback** when backend TTS disabled or fails |
| Gemini TTS (`*-preview-tts`) | High | growing | preview pricing | backend | Rejected for M5 — preview/unstable for production legal use |
| ElevenLabs | Best | limited Indian coverage | premium | backend | Rejected — new vendor, cost, weaker hi/ta/te/kn |

**Why Cloud TTS primary:** legal answers are read aloud verbatim; pronunciation and consistency matter. Cloud TTS is mature, supports the same Indian languages the product targets, takes SSML, and authorizes through the **same Google service account already configured for Firebase/Firestore/GCS** — one credential, no new trust boundary.

**Why keep a Web Speech fallback at all:** it is free and entirely client-side. For cost-sensitive deployments or when the synthesize endpoint errors, the frontend can fall back to `window.speechSynthesis.speak(...)` so the feature degrades to "still talks" rather than "silent." This is a pure frontend branch — no backend dependency.

**Output format:** `audio/mpeg` (MP3, 24 kHz) — universally playable in `<audio>`, small, no client decode work. Cloud TTS returns full audio per request; we return the whole blob (legal answers ≤ ~2 KB of text → sub-second synth, no need to stream audio in M5).

**Config additions:**
```python
tts_provider: str = "google_cloud"          # google_cloud | none (client-only)
tts_voice_default: str = "en-IN-Neural2-A"  # overridable per-user (§6)
tts_audio_encoding: str = "MP3"
voice_max_synthesize_chars: int = 5000      # cost + abuse cap
```

---

## 5. Backend APIs

**New file: `app/api/voice.py`** — router `prefix="/api/voice"`. **New file: `app/services/voice.py`** — STT/TTS wrappers (mirrors how `llm.py` wraps Gemini). Registered in `main.py` alongside the other routers. **The chat endpoint and `conversations.py` are not modified.**

### 5.1 `POST /api/voice/transcribe`

```
Auth:    required (existing get_current_user dependency)
Body:    multipart/form-data
           file:      UploadFile   (audio blob)
           language?: str          (BCP-47 hint, optional)
Returns: 200 {
           "text":        str,
           "language":    str,     # detected or hinted
           "duration_ms": int,
           "confidence":  float    # 0..1, top alternative
         }
Errors:  400 empty/too-short audio · 413 too large · 415 bad MIME ·
         422 no speech detected · 503 STT provider error
```

Stateless. Does **not** touch Firestore or a conversation. Pure audio → text. The frontend decides what to do with the text (preview, edit, send).

### 5.2 `POST /api/voice/synthesize`

```
Auth:    required
Body:    application/json
           text:     str
           voice?:   str           # overrides user default
           language?: str
Returns: 200 audio/mpeg  (binary MP3)
Errors:  400 empty text · 413 text > voice_max_synthesize_chars ·
         503 TTS provider error
Headers: Cache-Control: private, max-age=86400   (see §7 caching)
```

Stateless. Takes the assistant text the client already has from the SSE stream. No conversation lookup needed — the text is supplied directly, which also means TTS works for any text (e.g., re-reading an old message) without a DB round-trip.

### 5.3 What is explicitly NOT added

- No `/voice/chat` combined endpoint (would fork the chat path).
- No change to `POST /{id}/messages` request or response.
- No new fields *required* on `Message` or `Conversation` (see §7 for optional ones).

### 5.4 Service layer sketch (signatures only — design, not implementation)

```python
# app/services/voice.py
async def transcribe(audio: bytes, mime_type: str, language: str | None) -> Transcript: ...
async def synthesize(text: str, voice: str, language: str) -> bytes: ...   # returns MP3
```

These wrap the Cloud Speech / Cloud TTS clients exactly as `llm.py` wraps `genai.Client`, reusing `get_settings()` for config and the existing service-account credentials for auth.

---

## 6. Frontend UX

### Composer (reuses the existing chat composer)

- **Mic button** beside the send button. Tap-and-hold (push-to-talk) on desktop; tap-to-start / tap-to-stop on mobile (hold gestures are awkward on touch).
- **Recording state:** animated level meter + elapsed timer + "120 s max" countdown; a cancel (✕) discards without transcribing.
- **Transcribing state:** spinner on the composer; mic disabled until the transcript returns.
- **Transcript preview:** the returned text lands in the existing text input as an **editable draft**. The user edits if STT misheard, then presses send (which calls the unchanged chat endpoint).
- **Auto-send toggle:** when on, a returned transcript is sent immediately without the manual confirm tap. Still three sequential calls under the hood.

### Playback (on assistant messages)

- **Play (▶) button** on each assistant message bubble. Calls `/voice/synthesize` with that message's text, plays the returned MP3 in a hidden `<audio>`.
- **Autoplay toggle:** when on, the client calls synthesize automatically after the SSE `done` event and plays — subject to the mobile gesture rules in §12.
- **TTS fallback:** if `/voice/synthesize` errors or `tts_provider="none"`, fall back to `window.speechSynthesis` so playback still works.

### Hands-free / conversation mode (optional, behind a toggle)

Record → transcribe → auto-send → stream answer → auto-synthesize → play → re-arm the mic. A loop built entirely from the three existing calls; no new endpoint. Citations render visually as in M4 but are skipped by TTS (§7).

### Voice settings (the M5 settings page, foreshadowed in M4 scope)

A new `/settings` page (or section) storing client-side or per-user preferences:

- Preferred language (recognition hint + default TTS language)
- TTS voice selection (sample/preview button)
- Autoplay on/off, auto-send on/off
- Microphone device picker

Preferences are lightweight; store in `localStorage` for M5 (no backend persistence needed — avoids a new collection and stays inside "no memory system"). A future migration to a `users/{uid}/preferences` doc is non-breaking.

### Permissions & errors (surfaced inline)

Mic-permission-denied, no-mic-found, no-speech-detected, and network errors each map to a clear composer message with a retry affordance (see §11).

---

## 7. Storage Model

**Default: store nothing new.** Voice is transport. The transcript becomes the existing user `Message.content`; the assistant text is the existing assistant `Message.content`. Both already persist via the M4 path. **No `Message`/`Conversation` schema change is required for the default flow** — honoring "reuse existing conversation system."

### Optional persistence (off by default, documented for completeness)

If a deployment later wants audio retention (e.g., dispute trail), two additive, *optional* fields and two GCS prefixes cover it without breaking M4:

```python
# Message — additive optional fields, default None (no migration of existing docs)
audio_input_path:  str | None = None   # GCS path to the user's recorded audio
audio_output_path: str | None = None   # GCS path to cached TTS audio
```

```
GCS layout (only if retention enabled):
  voice/{uid}/{conversation_id}/{message_id}-in.webm      # user recording
  voice/{uid}/{conversation_id}/{message_id}-out.mp3      # synthesized answer
```

Reuses the existing `app/services/storage.py` blob abstraction (`upload_file`, `delete_file`) and the `documents/{uid}/...` ownership-pathing convention — no new storage service.

### TTS response caching (cost control, no Firestore)

Synthesis is deterministic for `(text, voice, language)`. Cache by content hash:

```
GCS: voice/tts-cache/{sha256(text|voice|lang)}.mp3
```

On `/voice/synthesize`: check cache → return blob if hit → else synthesize, store, return. The `Cache-Control: private, max-age=86400` header also lets the browser cache repeats. This is the single biggest TTS cost lever (re-reading the same message is free after the first synth).

**Citations are not synthesized.** TTS receives only the assistant prose, never the citation JSON — avoids reading "[1] [2]" aloud and keeps audio clean.

---

## 8. Security

| Concern | Control |
|---------|---------|
| **AuthN/Z** | Both endpoints use the existing `get_current_user` dependency. No anonymous access. |
| **Statelessness = no IDOR** | `/transcribe` and `/synthesize` touch no user-owned resource by ID, so there is no cross-user object to leak. They operate only on the caller-supplied bytes/text. |
| **DoS / cost abuse** | Hard caps: audio ≤ 120 s / ≤ 10 MB; synthesize text ≤ 5000 chars. Per-user rate limiting on both endpoints (STT and TTS each cost real money per call). |
| **MIME validation** | Reject anything outside the audio allowlist before calling the provider; never trust the client `Content-Type` alone — sniff the leading bytes. |
| **Privacy (sensitive legal audio)** | **No audio retention by default.** Recordings are transcribed in memory and discarded. Retention (§7) is opt-in and path-scoped to the owner UID. |
| **PII in transcripts** | Transcripts inherit the same protection as any chat message (per-user Firestore scoping from M2). No new exposure surface. |
| **SSML / TTS injection** | If SSML is ever enabled, escape user/assistant text before embedding. For M5, synthesize as **plain text** (no SSML markup interpolated from model output) — eliminates the injection class entirely. |
| **Served audio** | If retention is enabled, serve stored audio only via short-lived signed URLs scoped to the owner — never public blobs. Mirrors document access policy. |
| **Provider trust boundary** | STT/TTS stay inside Google Cloud (same service account as Firestore/GCS) — no audio leaves the existing trust boundary; no new vendor key to manage. |
| **Transcript review** | The editable-preview UX (§6) is also a safety control: the user sees exactly what will be sent before it reaches retrieval/LLM. |

---

## 9. Cost Analysis

Assumptions: average voice turn = 15 s of input audio, assistant answer ≈ 1,000 characters. Per **1,000 voice turns**.

### STT (Cloud Speech-to-Text v2)

- ~$0.016 / minute (standard models). 15 s = 0.25 min → **$0.004 / turn**.
- 1,000 turns → **~$4.00**.

### TTS (Cloud Text-to-Speech, Neural2)

- $16 / 1M characters. 1,000 chars/answer → **$0.016 / turn**.
- 1,000 turns → **~$16.00**, before caching.
- With cache hits on re-reads (conservatively 30%) → **~$11.00**.
- Web Speech fallback path → **$0**.

### LLM (unchanged from M4 — listed for the full picture)

- Gemini 2.5 Flash RAG turn ≈ existing M4 cost (~$0.001–0.003/turn). Voice adds nothing here.

### Per-1,000-turn summary

| Component | Cost | Notes |
|-----------|------|-------|
| STT (Cloud STT v2) | ~$4 | scales with audio seconds |
| TTS (Cloud TTS Neural2) | ~$11–16 | cacheable; $0 if Web Speech |
| LLM (M4, unchanged) | ~$1–3 | no voice surcharge |
| **Total voice surcharge** | **~$15–20 / 1,000 turns** | ≈ **$0.015–0.02 per voice turn** |

**Levers:** TTS cache (§7) is the biggest; Web Speech fallback zeroes TTS; the 120 s / 5,000-char caps bound the worst case. Voice roughly **5–10×** the per-turn cost of text chat — material but small in absolute terms.

---

## 10. Cloud Run Implications

| Factor | Impact | Handling |
|--------|--------|----------|
| **Request body size** | Audio upload up to 10 MB | Well under Cloud Run's 32 MB request limit. Enforce 10 MB at the app layer too. |
| **No transcode** | Cloud STT eats webm/opus directly | **No `ffmpeg`, no native binaries** in the image (the reason Cloud STT was chosen over Gemini in §3). CPU stays light. |
| **Memory** | One ≤10 MB audio blob + one ≤~200 KB MP3 per in-flight request | Default Cloud Run memory is ample; cap concurrency if many large uploads coincide. |
| **Latency / timeout** | STT ~0.5–2 s, TTS ~0.3–1 s | Far under the 300 s default request timeout. No timeout tuning needed. |
| **Streaming** | `/transcribe` and `/synthesize` are request/response, not SSE | Simpler than the chat endpoint — no `X-Accel-Buffering` concerns. The SSE chat step keeps its M4 headers. |
| **Cold start** | New Cloud Speech / TTS clients add small import/init cost | Lazy-init the clients (like `llm.py`'s `_get_client()`); reuse across requests. |
| **Egress** | Audio to Google APIs is in-region | Keep the Cloud Run region aligned with the Speech/TTS endpoint to minimize latency and egress. |
| **Credentials** | Cloud STT/TTS authorize via the existing service account | The Firebase service-account JSON's principal needs the `roles/speech.client` and Cloud TTS usage roles granted — an IAM change, not a code/secret change. |

No new infrastructure. Two stateless endpoints on the existing service; the only ops change is granting the service account Speech/TTS IAM roles and enabling those two APIs in the project.

---

## 11. Failure Handling

| Stage | Failure | Response |
|-------|---------|----------|
| Mic access | Permission denied | Inline composer error + "Enable microphone in browser settings"; mic button shows blocked state. |
| Mic access | No microphone found | Disable mic button; tooltip explains. |
| Recording | Exceeds 120 s | Auto-stop at limit, proceed to transcribe what was captured. |
| Recording | Too short (<0.4 s) | Discard silently; no STT call spent. |
| Upload | Network drop | Retry affordance; audio blob kept client-side until success or explicit cancel. |
| `/transcribe` | Empty / no speech detected | 422 → composer shows "Didn't catch that — try again." No message sent. |
| `/transcribe` | Bad MIME / too large | 415 / 413 → clear error; never reaches the provider. |
| `/transcribe` | STT provider error | 503 → "Transcription unavailable, type instead." Text input remains usable. |
| Chat step | (any) | **Unchanged from M4** — same SSE error handling, partial-message persistence, etc. Voice adds no new failure modes here. |
| `/synthesize` | TTS provider error | 503 → frontend falls back to Web Speech `SpeechSynthesis`; if that's unavailable, message stays text-only (no blocking error). |
| `/synthesize` | Text too long | 413 → truncate-and-warn or skip playback; the text answer is already fully visible. |
| Playback | Autoplay blocked (mobile) | Show a ▶ button requiring a tap (see §12); never error. |

**Principle:** voice failures degrade to text, never block the conversation. The text chat path is always the floor.

---

## 12. Mobile Considerations

- **Recording formats differ:** iOS/Safari `MediaRecorder` emits `audio/mp4` (AAC); Chrome/Android emit `audio/webm`. The `/transcribe` allowlist (§2) and Cloud STT auto-detection must accept both — already designed in.
- **Safari `MediaRecorder` support** arrived in iOS 14.3; gate the mic UI on `typeof MediaRecorder !== "undefined"` and hide it gracefully where unsupported (fall back to typing).
- **Autoplay restrictions:** iOS/Android block audio playback without a user gesture. **Autoplay TTS is best-effort** — on mobile, the first playback per session requires a tap; subsequent plays within the gesture-unlocked context can autoplay. The ▶ button is always present as the reliable path.
- **Touch ergonomics:** tap-to-start / tap-to-stop (not press-and-hold) on touch devices; large tap target; haptic/visual feedback on start/stop.
- **Data & battery:** Opus at ~16 kbps keeps 120 s ≈ 240 KB upload — friendly on mobile data. Stop the mic stream and release the track immediately on stop to save battery.
- **Lock screen / backgrounding:** if the tab backgrounds mid-recording, stop and transcribe what exists (don't attempt true background capture — out of scope for web).
- **Viewport:** the recording UI and transcript preview must fit the on-screen-keyboard-reduced viewport; reuse the existing responsive composer layout.

---

## 13. Future Compatibility

M5's three-step, transcript-as-unit design is intentionally a stepping stone. None of the following require breaking M5's schema or endpoints:

| Future capability | Path from M5 |
|-------------------|--------------|
| **Real-time partial transcripts** | Swap `/transcribe` to Cloud STT **streaming** recognition; the endpoint contract (audio in, text out) is unchanged. |
| **Full-duplex voice (barge-in)** | Add a WebSocket/Live endpoint *alongside* the REST trio (e.g., Gemini Live API). M5's REST endpoints remain for fallback and non-duplex clients. |
| **Streaming TTS audio** | Change `/synthesize` to return a chunked audio stream; clients that buffer the whole blob still work. |
| **Per-user voice preferences in backend** | Migrate the `localStorage` settings (§6) to `users/{uid}/preferences` — additive, no existing-data migration. |
| **Audio retention / e-discovery** | Flip on the optional `audio_input_path` / `audio_output_path` fields and GCS prefixes (§7) — additive, default-None, no migration. |
| **Single-vendor STT (Gemini)** | Switch `stt_provider="gemini"` once client-side encoding is added — config flag, no API change. |
| **Telephony (Twilio, etc.)** | A phone gateway can drive the same `/transcribe` → chat → `/synthesize` sequence server-side; the conversation system is already the system of record. |
| **Voice cloning / premium voices** | New `voice` values in `/synthesize`; the field already exists. |

**No M5 decision needs revision for any of the above** — the same property M4 had with respect to M5.

---

## 14. New & Modified Files

```
backend/app/
  api/
    voice.py             ← NEW: /api/voice/transcribe, /api/voice/synthesize
  services/
    voice.py             ← NEW: Cloud STT + Cloud TTS wrappers (mirrors llm.py)
  config/settings.py     ← MODIFIED: stt_/tts_/voice_ config additions (§3,§4)
  main.py                ← MODIFIED: register voice_router

frontend/src/
  features/voice/
    MicButton.tsx        ← NEW: record / level meter / countdown
    TranscriptPreview.tsx← NEW: editable draft from STT
    PlayButton.tsx       ← NEW: per-message TTS playback (+ Web Speech fallback)
    useRecorder.ts       ← NEW: MediaRecorder wrapper, format detection
    useVoiceSettings.ts  ← NEW: localStorage prefs
  features/settings/
    SettingsPage.tsx     ← NEW: voice prefs (language, voice, autoplay, auto-send)
  features/chat/
    Composer.tsx         ← MODIFIED: mount MicButton + transcript draft
    MessageBubble.tsx    ← MODIFIED: mount PlayButton on assistant messages
```

**Unchanged (the reuse guarantee):** `app/api/chat.py`, `app/api/conversations.py`, `app/services/rag.py`, `app/services/llm.py`, `app/models/conversation.py` (default flow), the SSE protocol, and the retrieval pipeline.

---

## 15. Summary of Decisions

| Area | Decision | Reason |
|------|----------|--------|
| Architecture | Voice = codec around text; transcribe → existing chat → synthesize | RAG embeds query text, so transcript must precede chat; enables total chat-endpoint reuse |
| Endpoints | Two new stateless: `/voice/transcribe`, `/voice/synthesize` | Chat endpoint stays byte-for-byte M4 |
| Transcript review | Editable preview before send (auto-send optional) | STT errors on legal terms are costly; correctness + safety control |
| STT provider | Cloud Speech-to-Text v2 | Ingests browser webm/opus with no transcode; strong Indian-language models; same service-account auth |
| STT alternative | Gemini native audio | Zero new dep, but webm container needs encoding/transcode — deferred |
| TTS provider | Cloud Text-to-Speech (Neural2), Web Speech fallback | Mature, multilingual, same auth; fallback gives $0 / always-talks degradation |
| TTS format | MP3 24 kHz, full blob | Universal `<audio>` playback; answers too short to need audio streaming |
| Storage | No new schema by default; optional additive audio fields + GCS prefixes | Honors "reuse conversation system / no memory" |
| TTS caching | GCS content-hash cache + browser `Cache-Control` | Largest TTS cost lever |
| Citations + TTS | Not synthesized | Clean audio; no schema conflict |
| Security | Auth on both; hard size/duration/char caps; no audio retention by default; plain-text TTS | Stateless = no IDOR; privacy for sensitive legal audio |
| Cloud Run | No transcode, no ffmpeg, lazy clients | Light CPU/memory; only IAM + API-enable ops change |
| Failure model | Voice degrades to text, never blocks | Text path is the floor |
| Settings | `localStorage` for M5 | Avoids new collection; stays within "no memory system"; non-breaking to migrate later |
```
