# Architecture

Optimising, in order, for: **simplicity → maintainability → scalability →
extensibility → developer experience → performance → security** — and, across all
of them, **free and open source first**. Every dependency choice is argued in
[`docs/TECH_STACK.md`](TECH_STACK.md); this document is about how the pieces
fit together.

Version 1 does one thing well: turn a pasted URL into stored, searchable,
exportable research. Every boundary below exists because a later version needs to
extend across it — not because it looked tidy.

---

## 1. Shape of the system

```
┌────────────┐    HTTP     ┌─────────────────────────────────────────┐
│  React     │  + JWT      │              FastAPI                    │
│  (Vite)    │ ──────────▶ │  api/  ·  services/  ·  db/  ·  workers/ │
└────────────┘ ◀────────── └──────────────┬──────────────────────────┘
                                          │ claims jobs
                                   ┌──────▼───────┐
                                   │  job queue   │  (a table, not a broker)
                                   └──────┬───────┘
                                          │
   ┌──────────────────────────────────────▼───────────────────────────────┐
   │  pipeline:  metadata → limits → download → audio → transcribe → store │
   │             (transcription runs locally — no external service)        │
   └───────────────────────────────────────────────────────────────────────┘
```

Two processes, one database, no broker, no third-party service in the request
path. That is the whole of V1.

---

## 2. Key decisions

### The job queue is a database table

`jobs` rows are claimed with a conditional `UPDATE ... WHERE status = 'queued'`,
which is atomic on both SQLite and Postgres. No Redis, no Celery, no extra
container to operate.

*Why not Celery?* A broker is the right answer at hundreds of concurrent jobs. At
agency scale — a handful of researchers submitting batches — it is three moving
parts bought for nothing. The `JobQueue` interface is narrow (`enqueue`, `claim`,
`complete`, `fail`) precisely so it can be re-implemented over a broker later
without the pipeline noticing.

### Storage is SQLAlchemy async, SQLite by default

SQLite makes `git clone && run` work with zero setup. `DATABASE_URL` switches to
Postgres with no code change; the schema uses no SQLite-specific column types.
Search is the one place the two genuinely differ, so it is abstracted (§3).

### Everything pluggable is a registry

Platforms, transcription providers, and export formats are each a small registry
keyed by name. Adding a YouTube Shorts pattern, a Deepgram provider, or a PDF
export is *adding a file*, never editing a dispatch `if/elif` chain.

### Metadata is fetched before anything is downloaded

`POST /api/videos/preview` probes with `yt-dlp` (`download=False`) and returns
title, thumbnail, duration, estimated size and platform, plus a limits verdict.
The UI shows this and lets the user drop items *before* a byte is transferred.
This is also the natural home for the V3 "is this worth researching?" pre-filter.

### Media files are temporary; transcripts are permanent

Video and audio are written to `WORK_DIR` and deleted as soon as the transcript is
stored (`KEEP_MEDIA=true` disables this for debugging). The durable asset is the
research, not the source file — which also keeps us clear of storing large
volumes of third-party video.

---

## 3. Module map

| Path | Responsibility |
|---|---|
| `app/api/` | HTTP only: validation, serialisation, status codes. No business logic. |
| `app/platforms/` | URL → `ParsedURL`. Registry of `PlatformAdapter`s (`youtube`, `instagram`). |
| `app/services/metadata.py` | `yt-dlp` probe → `VideoMetadata`. |
| `app/services/limits.py` | Pure functions: metadata + settings → allow/reject verdict. |
| `app/services/media.py` | Download + ffmpeg audio extraction + chunking. `MediaBackend` protocol so tests fake it. |
| `app/services/transcription/` | `TranscriptionProvider` registry: `faster_whisper` (default, local, free) and `stub` (tests). No paid provider exists. |
| `app/services/users.py` | Accounts: creation, lookup, credential checking. |
| `app/core/security.py` | bcrypt password hashing and JWT issue/verify. |
| `app/services/export/` | `Exporter` registry: txt, md, json, srt, vtt, docx, xlsx (+ bulk ZIP). |
| `app/services/search.py` | `SearchBackend`: SQLite FTS5, portable `LIKE` fallback. |
| `app/services/pipeline.py` | The stage machine. The only module that knows the *order* of things. |
| `app/workers/` | Polls the queue, runs the pipeline, handles retries and crash recovery. |
| `app/db/models.py` | `Video`, `Job`, `Transcript`, `TranscriptSegment`. |

The dependency rule is one-directional: `api → services → db`. `services` never
imports `api`; `db` imports nothing above it.

---

## 4. The pipeline

```
QUEUED
  → FETCHING_METADATA   yt-dlp probe, no download
  → CHECKING_LIMITS     duration / filesize / platform  ── reject ──▶ FAILED
  → DOWNLOADING         yt-dlp, progress reported per-percent
  → EXTRACTING_AUDIO    ffmpeg → 16 kHz mono WAV (what ASR models want)
  → TRANSCRIBING        provider; long audio auto-chunked, timestamps re-offset
  → STORING             transcript + segments + search index, one transaction
  → COMPLETED
```

Each stage is an `async` function with the same signature, so stages can be
reordered, skipped, or inserted without touching the others. V2's analysis stage
is one entry in this list, appended after `STORING`.

Failures record the stage they happened in, the error, and whether they are
retryable. Network and rate-limit errors retry with exponential backoff up to
`JOB_MAX_ATTEMPTS`; a 404 or an over-limit video does not retry, because it never
will succeed.

---

## 5. Data model

```
Video ──1:N── Job                     one row per submitted URL, deduplicated
  │                                   on (platform, platform_video_id)
  └──1:N── Transcript ──1:N── TranscriptSegment
```

- **`Video`** holds metadata *and* `raw_metadata` (the full provider payload as
  JSON). Keeping the raw payload means V2/V3 can mine fields — view counts, upload
  date, hashtags — that V1 never modelled, without re-downloading anything.
- **`Transcript`** is versioned per video rather than overwritten: re-transcribing
  with a better model adds a row. The API returns the latest by default.
- **`TranscriptSegment`** carries `start`/`end`, which is what makes SRT and VTT
  export real rather than approximated, and what a future "jump to this quote"
  feature needs.

`Analysis` (V2) attaches to `Transcript` by FK. Nothing in V1 needs to change to
accommodate it — which is the test of whether this model was drawn correctly.

---

## 6. Search

`SearchBackend` has one method: `search(query, filters, limit, offset)`.

- **SQLite** → an FTS5 virtual table (`transcript_fts`) kept in sync on write,
  giving real ranked full-text search and snippet highlighting locally.
- **Anything else** → a portable `LIKE`-based backend.

When the corpus outgrows both — V3's "search thousands of transcripts" and
"ask questions about previous research" — the replacement is a third backend
(Postgres `tsvector`, or a vector store for semantic search) behind the same
method. Search callers never learn which one they got.

---

## 7. Extension points

### Adding a platform

```python
# app/platforms/tiktok.py
class TikTokAdapter(PlatformAdapter):
    name = "tiktok"
    display_name = "TikTok"
    _PATTERNS = (re.compile(r"..."),)

    def parse(self, url: str) -> ParsedURL: ...
```

Register it in `app/platforms/__init__.py`. Validation, preview, download and the
UI's platform badge all pick it up — `yt-dlp` already handles the extraction.

### Adding a transcription provider

Subclass `TranscriptionProvider`, implement
`async def transcribe(audio_path, language) -> TranscriptionResult`, register the
name. The pipeline is unchanged.

### Adding an export format

Subclass `Exporter` (`format`, `extension`, `content_type`, `render()`), register
it. It appears in the API enum, the bulk ZIP, and the UI dropdown automatically.

### V2 — AI analysis, behind an `LLMProvider`

Add `app/services/analysis/` with an `Analysis` model FK'd to `Transcript` and
one stage appended to the pipeline. Analysis reads *stored* transcripts, so it
can also be run as a backfill over everything already collected — the reason
transcripts are stored with segments and raw metadata.

The model access itself goes behind the same registry pattern already used for
transcription, so the choice of model is configuration rather than architecture:

```python
# app/services/llm/base.py
@dataclass(frozen=True)
class LLMResponse:
    text: str
    model: str
    input_tokens: int | None = None
    output_tokens: int | None = None     # so cost can be tracked per analysis

class LLMProvider(ABC):
    name: str

    @abstractmethod
    async def complete(
        self,
        prompt: str,
        *,
        system: str | None = None,
        max_tokens: int = 2048,
        schema: dict | None = None,      # structured output where supported
    ) -> LLMResponse: ...

    def validate_configuration(self) -> None:
        """Raise ConfigurationError if this provider cannot run."""
```

Implementations register by name exactly as transcription providers do:
`ollama` (free, local — the default, keeping V2 zero-cost if quality allows),
then `claude`, `openai`, `gemini`, `deepseek`, `groq` as paid options selected by
`LLM_PROVIDER`. Nothing above the provider knows or cares which is active.

This is deliberately **not** built in V1: unused abstractions are complexity
without a customer. The contract is specified here so V2 starts from a decision
already made, and the registry pattern it will use is already working in three
places (`platforms/`, `transcription/`, `export/`).

### V3 — research system

Cross-transcript work (compare creators, detect trends, generate scripts) reads
the same tables and reuses the search backend. It is a new service package plus
new routes; the V1 collection path is untouched.

---

## 8. Security

- **Auth**: JWT bearer tokens. Passwords are bcrypt-hashed with a per-password
  salt and never stored or logged in the clear. Auth is applied once, in
  `app/api/router.py`, to everything except `/api/health` (the container probe
  cannot sign in) and `/api/auth/login` — so a new router cannot accidentally
  ship unprotected.
- **Token revocation**: a JWT is valid until it expires, so tokens are short
  (12 hours) *and* every request re-loads the account. Deactivating someone takes
  effect on their next request even though their token is still technically
  valid. `tests/test_auth.py` proves this.
- **Signing key**: the app refuses to start outside development if `JWT_SECRET`
  is still the shipped default or shorter than 32 characters.
- **SSRF**: URLs must parse to a registered platform before any fetch. Arbitrary
  hosts are rejected at validation, not at download.
- **Command injection**: `ffmpeg` and `yt-dlp` are invoked with argument *lists*,
  never a shell string. No user input reaches a shell.
- **Path traversal**: work files use server-generated UUID paths; user-supplied
  titles are sanitised before being used in export filenames.
- **Resource exhaustion**: duration, filesize and batch-size limits are enforced
  before download; worker concurrency is bounded.
- **Secrets**: only ever from environment. `.env` is gitignored; `.env.example`
  carries names, never values.
