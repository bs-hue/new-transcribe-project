# Technology & Design Decisions

**Product:** AI Content Research Platform — Module 1: Bulk Transcript Agent
**Purpose:** a single register of **every technology and pattern we use, why we chose it, what we rejected, and what it costs to change our mind.** If a choice is questioned later, the answer lives here.
**Document status:** Approved (2026-07-28)
**Last updated:** 2026-07-28

---

## 1. How to read this document

Every entry follows the same shape:

- **What** — the concrete thing we install or the pattern we apply.
- **Why** — the reason it earns its place *in this project, under our constraints*.
- **Instead of** — the credible alternative we rejected, and why.
- **Reversal cost** — how expensive it is to swap later. This is the column that matters most: we accept simple-but-limited choices **only** where reversal is cheap.

Three constraints drive nearly every decision (see `PROJECT_CONTEXT.md` §4):

1. **No GPU, limited RAM** in production.
2. **Small disk** — media is transient, never retained.
3. **Single modest VPS** — one box runs API, worker, and DB.

> **Dependency pin policy:** exact versions are pinned in `pyproject.toml` / `package.json` at Phase 0, not here. Maintenance claims below (e.g. "unmaintained") must be **re-verified at pin time** — a library's health can change between this document and installation.

---

## 2. Architecture & structure

### 2.1 Clean Architecture (ports & adapters)

- **What:** four layers — `interface → application → domain`, with `infrastructure` implementing domain ports. Domain imports nothing.
- **Why:** the product's whole premise is that infrastructure will be swapped — in-process queue → Redis worker, polling → SSE, faster-whisper → an API, local disk → S3. Ports make each of those an adapter swap instead of a rewrite. It also makes the business rules (job state machine, failure isolation) unit-testable with **zero I/O**, which matters because our real dependencies (whisper, FFmpeg, YouTube) are slow, heavy, and flaky to test against.
- **Instead of:** a conventional FastAPI layout (`routers/`, `services/`, `models/`). Faster to start, but business logic ends up entangled with SQLAlchemy and FastAPI types, and every infrastructure swap becomes surgery.
- **Reversal cost:** very high (it *is* the codebase shape). This is the one decision we're deliberately locking in up front.
- **Honest cost we accept:** more files, more indirection, and slower initial velocity. Justified only because the swap list above is real, not hypothetical.

### 2.2 Modular monolith (bounded contexts), not microservices

- **What:** one deployable backend, internally split into `modules/auth`, `modules/transcription`, plus a shared kernel. Future modules (Insights, RAG, Translation) are new folders.
- **Why:** we get module boundaries and independent reasoning without paying for network hops, distributed tracing, or multiple containers — on one small VPS, microservices would consume the box in overhead alone. Boundaries now mean a module *could* be extracted later if it ever needs its own scaling profile.
- **Instead of:** microservices (too heavy for this host); or a single undifferentiated app (no seams for future modules).
- **Reversal cost:** low-to-moderate — a clean module can be lifted into its own service because it already talks through ports.

### 2.3 Monorepo, fully separated frontend and backend

- **What:** `backend/` and `frontend/` in one repository, sharing nothing at runtime; the API contract is the only coupling.
- **Why:** one repo keeps the contract, specs, and compose files versioned together and reviewable in one PR. Separation keeps deploys independent (static assets vs Python service) and lets the frontend be replaced without touching the backend.
- **Instead of:** two repos (contract drift, two-PR changes for one feature); or a coupled full-stack framework (violates the separation rule in `CLAUDE.md`).
- **Reversal cost:** low — splitting a monorepo later is mechanical.

---

## 3. Backend runtime

| What | Why | Instead of | Reversal cost |
|---|---|---|---|
| **Python 3.11+** | The STT and media ecosystem (faster-whisper, yt-dlp) is Python-native; 3.11 brings meaningful interpreter speedups and `TaskGroup`/`ExceptionGroup` for structured concurrency in the pipeline. | Node/Go — would force us to shell out to Python for STT anyway, losing type-safe integration. | Very high. |
| **FastAPI** | Async-first (our API is I/O-bound), Pydantic validation at the boundary is exactly what Clean Architecture wants, and OpenAPI generation gives the frontend a machine-readable contract for free. | Django (ORM/admin-centric, heavier than we need, sync-first heritage); Flask (would need assembling validation, async, and OpenAPI by hand). | Moderate — the interface layer is thin by design; use cases are framework-free. |
| **Uvicorn, single worker in v1** | ASGI server FastAPI is built against. **One worker** because v1 keeps queue state, the concurrency semaphore, and rate-limit counters **in process** — multiple workers would each hold their own copy and silently break all three. | Multiple workers/Gunicorn — deferred until the queue moves to Redis/ARQ, which is what makes multi-process safe. | Low — a config change once ARQ lands. |
| **pydantic-settings** | Typed, validated 12-factor config with one source of truth (`core/config.py`); fails fast at boot on a bad env var instead of at 3am on a bad code path. | Raw `os.environ` (untyped, fails late); dynaconf (more machinery than we need). | Low. |
| **structlog** (structured logging) | NFR-O1 needs correlation IDs (`job_id`, `item_id`) on every line so a single item's journey through five pipeline stages is greppable. Structured key-values also stay machine-parseable if we add log shipping later. | stdlib `logging` with f-strings — human-readable but effectively unqueryable across a long-running batch. | Low — logging is behind `core/logging.py`. |

---

## 4. Data layer

| What | Why | Instead of | Reversal cost |
|---|---|---|---|
| **SQLAlchemy 2.x (typed)** | Mature, and the 2.0 typed API works with mypy, so repositories are type-checked. Lets one model set target both SQLite and Postgres — the core requirement for dev/prod parity. | Raw SQL (two dialects to hand-maintain); Tortoise/SQLModel (thinner ecosystems; SQLModel blurs the domain/persistence line we're deliberately keeping sharp). | High — but confined to `infrastructure`, since use cases only see repository ports. |
| **Alembic, from the first migration** | Production DBs are never rebuilt from scratch. Having migrations before the first table means we never face a "how did prod get this schema?" gap. Autogenerate drafts, humans review. | `create_all()` in dev then retrofitting migrations — guarantees a painful reconciliation later. | N/A — foundational. |
| **SQLite (dev) → PostgreSQL (prod)** | SQLite makes local dev zero-setup and CI fast. Postgres in prod for real concurrency, proper `TIMESTAMPTZ`, and JSONB. The schema deliberately avoids engine-specific features (see `DATABASE_DESIGN.md` §7) so parity holds. | Postgres everywhere (heavier local setup, slower CI); SQLite in prod (single-writer locking would serialize the API against the worker on the same box). | Low by design — that's what the portability rules buy us. |
| **psycopg 3** | Current, actively maintained Postgres driver with both sync and async support, so an async repository path later needs no driver change. | psycopg2 (legacy branch); asyncpg (fast, but SQLAlchemy-async-only — less flexible for our mixed sync worker/async API shape). | Low. |
| **Repository + Unit of Work** | Gives use cases a domain-shaped persistence API and one explicit transaction boundary per use case — so a half-written job can't be committed. Also the seam that makes domain tests I/O-free. | Calling sessions directly in use cases — leaks SQLAlchemy inward and makes transaction scope implicit. | Moderate. |
| **UUIDv4 primary keys** | Non-guessable IDs in URLs (no enumeration of other users' jobs), and IDs can be generated before insert — useful when creating a job and N items in one transaction. | Auto-increment integers (enumerable, and awkward for pre-insert generation). | High (they're in the API contract). |
| **Enums stored as `VARCHAR` + domain validation** | Native PG enums require a migration to add a value; our status/stage vocabularies will grow. Validation belongs in the domain anyway. | Native PG enums (migration friction, SQLite parity problems). | Low. |
| **`progress_events` table, writes disabled by default in v1** | Kept in the schema for future SSE/audit, but `PROGRESS_HISTORY_ENABLED=false` in v1 so we don't pay a DB write per progress tick on a small box with no reader. Flip it on the day something reads it. | Writing history nobody reads (pure write amplification); or omitting the table (a migration later, plus no audit trail option). | Low — a config flag. |

---

## 5. Authentication & security

| What | Why | Instead of | Reversal cost |
|---|---|---|---|
| **JWT access token, short TTL (15 min)** | Stateless verification means no DB hit per request — which matters when the box is busy transcribing. Short TTL bounds the damage of a leaked token. | Server-side sessions (DB lookup per request); long-lived JWTs (unrevocable window measured in days). | Moderate. |
| **Opaque refresh token, hashed at rest, rotated on use** | Long-lived credentials must be **revocable** — so the server stores a hash (a DB leak yields no usable tokens) and rotation lets us detect replay of a stolen token. Opaque rather than JWT because its only job is a DB lookup. | JWT refresh tokens (revocation needs a blocklist anyway — same DB hit, more complexity). | Moderate. |
| **Refresh token in an HttpOnly, Secure, SameSite=Lax cookie** *(decision #1, resolved)* | JavaScript cannot read it, so an XSS bug can't exfiltrate the long-lived credential — the single highest-value hardening available to a browser app. The access token stays in memory (never `localStorage`), so XSS can at worst borrow a 15-minute token. | Refresh token in the response body + `localStorage` — trivially stolen by any XSS. | Low-moderate — the API contract supports both transports. |
| **CSRF defence: `SameSite=Lax` + a required `X-CSRF-Token` double-submit on `/auth/refresh` and `/auth/logout`** | A cookie-borne credential is automatically attached by the browser, so cookie-authenticated endpoints need CSRF protection. `Lax` blocks cross-site POSTs in current browsers; the double-submit token is the belt to that braces. Only the two cookie-reading endpoints need it — everything else uses the `Authorization` header, which is not auto-attached and therefore not CSRF-able. | Relying on `SameSite` alone (one browser quirk from being the only line of defence); CSRF tokens on every endpoint (cost with no benefit for Bearer-auth routes). | Low. |
| **argon2 via `argon2-cffi`** | Argon2id is the current password-hashing recommendation and is memory-hard; `argon2-cffi` is maintained and used directly, with tuned parameters. **Deliberately not `passlib`** — it has been effectively unmaintained for years and has known friction with modern `bcrypt` releases; a dead dependency in the auth path is exactly where we don't want one. *(Re-verify maintenance status at pin time.)* | passlib+bcrypt (unmaintained wrapper); plain bcrypt (fine, but weaker than Argon2id and has a 72-byte input truncation footgun). | Low — hashing is behind `core/security.py`, and the scheme is recorded per hash for transparent rehashing. |
| **PyJWT** | Actively maintained, minimal, does exactly one job. **Deliberately not `python-jose`**, which has seen little maintenance and carries a broader crypto surface than we need. *(Re-verify at pin time.)* | python-jose; authlib (a full OAuth framework — far more than JWT signing). | Low. |
| **RBAC with an `admin`/`user` role model, M:N `user_roles` table** | *I flagged this table as over-engineering in review and then reversed myself — here's why:* the join table is ~10 lines and one migration, while the alternative (single `role` column) forces `PATCH /users/{id}/roles` to reject the array shape it already publishes, and buys a guaranteed future migration + API change. Keeping M:N costs almost nothing today and keeps the contract honest. | Single `role` column (contract wart + certain future migration); a full permission/scope system (no requirement yet). | Low either way. |
| **Bootstrap admin from env, created only if absent** | A fresh deploy needs a first admin without a manual SQL step (success metric: "zero manual server steps"). | Manual DB insert on every deploy (error-prone, undocumented). | Low. |
| **`slowapi` for rate limiting, in-memory in v1** | NFR-S5 requires limits on auth and job creation. In-memory is correct **because we run one worker**; the same library swaps to a Redis backend when we scale out — the same event that makes multi-worker safe. | A custom middleware (reinvention); Nginx-level limits (can't express per-user quotas, only per-IP). | Low. |
| **Admin sees transcript *metadata* only; content access is audit-logged** *(decision #4, resolved)* | Users' transcripts can contain confidential material. Admins get everything they need to operate (states, errors, durations, ownership) without a standing right to read content. If a support case ever needs content, it goes through an explicit, logged path — so access is accountable rather than ambient. | Admins read everything (a privacy liability with no operational payoff); admins read nothing ever (blocks legitimate support). | Low. |

---

## 6. Async execution, progress & reliability

### 6.1 `QueueService` port — FastAPI BackgroundTasks in v1, Redis + ARQ later *(decision #2, approved)*

- **What:** `RunJobItem` is a plain callable use case; the queue adapter decides where it runs. v1 = in-process BackgroundTasks with a bounded semaphore. Future = ARQ worker.
- **Why now:** zero extra infrastructure on a box that has none to spare, and no Redis to operate. Why ARQ later: it's async-native (matches FastAPI, unlike Celery's sync-first design), far smaller than Celery, and persists the queue so restarts don't lose work.
- **Reversal cost:** low — a new adapter plus a compose service. **No business-logic change**, which is the entire point of the port.
- **Accepted v1 limitation (stated plainly):** BackgroundTasks die with the process. An API restart mid-batch abandons in-flight items. Mitigated by the lease recovery below; **removed** by ARQ.

### 6.2 CPU-bound work is isolated from the API process *(new safeguard)*

- **What:** yt-dlp and FFmpeg run as **subprocesses** (`asyncio.create_subprocess_exec`). faster-whisper runs in a **`ProcessPoolExecutor`** sized by `MAX_CONCURRENT_TRANSCRIPTIONS` (default **1**), with CTranslate2 thread counts pinned (`cpu_threads`/`OMP_NUM_THREADS`).
- **Why:** "off the event loop" isn't sufficient — whisper is CPU- and memory-hungry, and in-process it would contend with request handling for the GIL and for RAM. A separate process gives the OS scheduler a fair shot at keeping the API responsive, and pinning thread counts stops CTranslate2 from grabbing every core and thrashing a small box. Subprocesses for the media tools also give us free timeout-and-kill semantics.
- **Instead of:** a thread pool (GIL contention, and no way to hard-kill a hung native call).
- **Reversal cost:** low — contained in the transcription adapters.

### 6.3 Crash recovery via leases *(new safeguard)*

- **What:** `job_items` carry `lease_owner` and `lease_expires_at`. A worker claims an item by taking a lease and renews it as a heartbeat. On startup — and periodically — a reaper requeues items whose lease has expired, incrementing `attempts`.
- **Why:** "mark interrupted items recoverable on startup" needed an actual mechanism. Without a lease you must choose between requeueing everything mid-flight (double work, duplicate transcripts) and stranding items in `processing` forever. A lease distinguishes *alive* from *abandoned* without a distributed lock, and the same mechanism keeps working unchanged under ARQ.
- **Instead of:** blanket requeue on boot (unsafe); manual operator intervention (violates "zero manual server steps").
- **Reversal cost:** low — two columns and a reaper task.

### 6.4 Per-stage timeouts *(new safeguard)*

- **What:** each stage gets its own wall-clock budget (`DOWNLOAD_TIMEOUT`, `EXTRACT_TIMEOUT`, `TRANSCRIBE_TIMEOUT`, `SUMMARIZE_TIMEOUT`); exceeding it kills the subprocess/worker and fails the item with `STAGE_TIMEOUT`.
- **Why:** with a concurrency cap of 1, **one hung item blocks the entire system indefinitely.** A stalled yt-dlp on a dead connection is a realistic, non-exotic failure. Timeouts convert an outage into a single failed item.
- **Reversal cost:** trivial (config).

### 6.5 Retry policy *(decision, resolved — retry is in v1)*

- **What:** errors are classified **retryable** (network, rate-limited source, timeout) vs **terminal** (private/removed video, unsupported source, too long, DRM). Retryable items retry automatically up to `MAX_ATTEMPTS` (default **3**) with exponential backoff + jitter via `next_retry_at`. Terminal errors never retry. Users can also retry a single failed item manually.
- **Why:** the `attempts` column existed with no policy behind it. yt-dlp failures are frequently transient, so auto-retry is the difference between a 95% success rate and a frustrating one. Classification is essential — retrying a deleted video three times just burns the box's scarce CPU and delays other users' work. Manual retry is in v1 because per-item failure is *expected* here, and forcing a user to resubmit the whole batch to recover one URL is a poor experience.
- **Instead of:** no retry (fragile); blind retry-everything (wastes constrained resources on hopeless items).
- **Reversal cost:** low — policy lives in the domain, so it's tunable without touching adapters.

### 6.6 Cooperative cancellation *(new design)*

- **What:** `POST /jobs/{id}/cancel` sets `cancel_requested_at`. Queued items cancel immediately. In-flight items: download/extract subprocesses are **killed outright**; transcription checks the flag **between segments** (faster-whisper yields segments as a generator) and aborts at the next segment boundary.
- **Why:** the API had a cancel endpoint with no defined mechanism. Segment-level checkpoints give us near-immediate cancellation of the longest stage without the fragility of killing a process mid-write, and partial work is simply discarded. Users cancelling a wrong 3-hour paste must not have to wait it out — on a 1-concurrency box, that's the difference between a minor mistake and an hour of blocked queue.
- **Instead of:** kill the whole worker process (loses the pool and any sibling state); ignore cancellation for in-flight items (unacceptable UX at our throughput).
- **Reversal cost:** low.

### 6.7 Disk-exhaustion guard & pre-flight metadata check *(new safeguard)*

- **What:** before download, `yt-dlp --dump-json` resolves duration/size/title/live-status **without** fetching media. Items over `MAX_VIDEO_DURATION` (default 2h) are rejected as terminal. Downloads also require configurable free-space headroom (`MIN_FREE_DISK_MB`); if unmet, the item waits rather than filling the disk. Media is deleted in a `finally` block — on failure paths too, not just success.
- **Why:** this is the **highest-impact gap** relative to our own stated constraints. On a small disk, one oversized video can fill the volume, which takes down Postgres and the whole application — a total outage caused by a single bad URL. Metadata-first also means we reject impossible work *before* spending bandwidth and CPU, and gives us the title for the UI early. Cleanup in `finally` matters because failures are the common case where temp files leak.
- **Instead of:** documenting a duration limit without enforcing it (the current spec's position); cleanup only after success (leaks on every failure).
- **Reversal cost:** trivial.

### 6.8 `ProgressService` port — DB polling in v1, SSE later

- **What:** the pipeline writes progress through a port; v1 persists latest state on `job_items` and the client polls `GET /jobs/{id}/progress`. Polling only while items are non-terminal and the tab is focused, with backoff.
- **Why:** polling needs no persistent connections, no extra infrastructure, and survives restarts trivially. SSE would hold an open connection per viewer on a box already short on resources, for a job measured in minutes — the responsiveness gain isn't worth it yet. The port means the pipeline code is identical either way.
- **Reversal cost:** low — add a transport adapter; the write side never changes.

---

## 7. Media pipeline & speech-to-text

| What | Why | Instead of | Reversal cost |
|---|---|---|---|
| **yt-dlp, invoked as a subprocess** | The only tool that credibly keeps pace with extractor breakage across many sites. Run as a subprocess (not imported) so we get **hard timeouts, clean kills for cancellation, and crash isolation** — a segfault or memory blow-up in an extractor can't take the API down with it. | Importing yt-dlp in-process (a hung or crashing extractor becomes our problem); pytube (narrower, breaks more often). | Moderate — behind `MediaDownloader`. |
| **FFmpeg → mono 16 kHz WAV** | Whisper models are trained on 16 kHz mono; converting once up front avoids resampling surprises and shrinks the file we hand to the model. FFmpeg is the only realistic choice for format coverage. | Passing source audio directly (unpredictable sample rates/codecs); Python audio libraries (would shell out to FFmpeg anyway). | Low. |
| **faster-whisper (CTranslate2 backend), CPU + `int8`** | Roughly 4× faster and materially lighter on memory than reference `openai-whisper` for identical model weights — decisive when the production box has no GPU and little RAM. `int8` quantization cuts memory again for a small accuracy cost we accept. Exposes segment-level generators, which is what makes §6.6 cancellation possible. | `openai-whisper` (too slow/heavy for CPU-only); whisper.cpp (fast, but a C++ binding boundary and weaker Python ergonomics); a hosted STT API (per-minute cost, and sends user content to a third party — kept as the documented fallback if the host can't run local STT). | Low — behind `TranscriptionProvider`, which is exactly the escape hatch if benchmarking disappoints. |
| **Default model `small`, configurable** *(decision #3, approved)* | Best accuracy-per-CPU-second on a small box; `tiny`/`base` are noticeably worse on accented speech, `medium` is too slow to be pleasant CPU-only. Configurable per job so users can trade speed for accuracy knowingly. | A fixed model (no escape valve); `medium` default (poor first impression on throughput). | Trivial (config). |
| **Silero VAD filter enabled** | Skips silence, so we don't spend scarce CPU transcribing nothing, and it suppresses a known Whisper failure mode where silence produces hallucinated text. | No VAD (slower and measurably noisier output). | Trivial. |
| **Exports derived on demand (TXT/SRT/VTT/JSON)** | Formatting is microseconds from data we already hold; storing four files per transcript would multiply disk use for zero benefit on a disk-constrained box. Formatters are **pure functions** — trivially unit-testable, no I/O. | Pre-generating and storing export files (disk cost, cache invalidation, no upside). | Low — `StorageService` can cache later if a real hot path appears. |
| **Playlist/channel URLs rejected with a clear error** *(new safeguard)* | Pre-flight metadata reveals a playlist. One pasted playlist URL could silently expand into hundreds of downloads — blowing through batch limits, disk, and CPU on a box sized for ~1 concurrent job. Explicit rejection with guidance beats a silent resource bomb. Playlist *expansion* is a deliberate fast-follow, gated behind its own limits. | Silent expansion (resource exhaustion); silent single-video fallback (surprising and wrong). | Low. |
| **`MAX_URLS_PER_BATCH = 25`** *(decision #3, approved)* | At CPU-only throughput, 25 items is already a long queue; larger batches mostly create abandoned work and misleading ETAs. | Unlimited (queue starvation, unbounded disk churn). | Trivial. |

---

## 8. LLM summaries (the optional "Agent")

| What | Why | Instead of | Reversal cost |
|---|---|---|---|
| **`LLMProvider` port; external API only; disabled by default** | No GPU and limited RAM make local inference impossible on the target host — a hard constraint, not a preference. Disabled by default means no accidental spend and no surprise data egress; opt-in is the honest default for a feature that costs money per use and sends user content off-box. | A local LLM (physically won't fit); a hardcoded vendor SDK (locks us in and makes tests require network). | Low — one adapter. |
| **Summaries never block transcript completion** | Transcription is the product; summarization is a bonus. A provider outage, quota error, or timeout must degrade to "summary unavailable," not lose a transcript that cost real CPU minutes to produce. | Coupling the two (an LLM outage would waste completed transcription work). | N/A — a domain rule. |
| **Per-user quotas + timeouts on summarization** | Long transcripts mean large token counts; unbounded use turns a nice-to-have into an unbounded bill. | Trusting usage patterns. | Low. |

---

## 9. Frontend

| What | Why | Instead of | Reversal cost |
|---|---|---|---|
| **React + TypeScript** | Largest component ecosystem (shadcn/ui depends on it) and static types across the API boundary catch contract drift at compile time rather than in the browser. | Vue/Svelte (fine, but shadcn/ui and the surrounding ecosystem are React-first). | Very high. |
| **Vite** | Near-instant dev server and a simple static production build — which is all we need, since the backend is entirely separate and there's no SSR requirement. | Next.js (an SSR/server framework we'd fight against, and it blurs the frontend/backend separation `CLAUDE.md` requires); CRA (deprecated). | Low-moderate. |
| **Tailwind CSS** | Utility classes keep styling colocated with markup and make a consistent spacing/color scale enforceable; it's also shadcn/ui's assumed foundation. | CSS Modules / styled-components (more ceremony, weaker design-token consistency). | High (it's in the markup). |
| **shadcn/ui (Radix primitives + CVA)** | Components are **copied into the repo**, not imported from a package — so we own and can modify them, with no version-upgrade risk in our UI layer. Radix underneath gives correct keyboard interaction, focus trapping, and ARIA semantics, which is most of how we reach WCAG 2.1 AA without hand-rolling accessibility. | MUI/Chakra (heavier, opinionated theming, harder to restyle); hand-built components (we'd reimplement accessibility badly). | Moderate — but the code is ours already. |
| **TanStack Query (React Query)** | Server state here is *exactly* its use case: caching, background refetch, and **interval polling with automatic stop conditions** for job progress. Doing this by hand with `useEffect` is where subtle leaks and runaway polling live. | Redux/Zustand for server data (manual cache and invalidation); raw `useEffect` fetching (bug farm). | Moderate. |
| **React Router** | Standard client-side routing with the nested-layout and route-guard support the app shell and admin routes need. | TanStack Router (excellent typed routing, smaller ecosystem); no router (untenable). | Low. |
| **React Hook Form + Zod** | Uncontrolled inputs keep re-renders minimal on the multi-URL form, and Zod schemas give one validation definition that's also a TypeScript type — so URL/option validation can't drift from its types. | Formik (heavier, less type-friendly); manual form state (repetitive, error-prone). | Low. |
| **Access token in memory, never `localStorage`** | `localStorage` is readable by any injected script; an in-memory token dies with the tab and is refreshed via the HttpOnly cookie. This is the client half of §5's threat model. | `localStorage`/`sessionStorage` (XSS-exfiltratable). | Low. |
| **Sonner (toasts), Lucide (icons)** | Both are shadcn/ui's defaults — accessible, tiny, and already consistent with the component set. | Custom notification/icon systems (no benefit). | Trivial. |
| **Transcript viewer: split-pane on desktop, tabs on mobile** *(decision, resolved)* | Reading text while scanning timestamps is a genuine two-pane task on a wide screen; forcing tabs there would mean constant toggling. Below `lg`, tabs are the only sane option. | Tabs everywhere (wastes desktop space); split-pane everywhere (unusable on phones). | Low. |
| **Neutral zinc palette + a single indigo accent** *(placeholder, decided)* | Unblocks Phase 0/3 with a professional, high-contrast, AA-compliant default. It's expressed purely as CSS variables, so adopting a real brand later means editing token values — not components. | Waiting for brand (blocks UI work); baking hex values into components (a costly rebrand). | Trivial by construction. |

---

## 10. Packaging, deployment & operations

| What | Why | Instead of | Reversal cost |
|---|---|---|---|
| **Docker + Compose** | FFmpeg, yt-dlp, and Python native deps make "works on my machine" a real hazard; a container pins the whole system, and Compose runs the identical topology in dev and on the VPS. It's also our hedge on the host question — if the Hostinger plan can't run containers, we learn that immediately. | Bare-metal install (unreproducible, fragile); Kubernetes (absurd overhead for one box). | Moderate. |
| **Nginx serving built static assets, proxying `/api`** | Static files should be served by a static file server, not Python. Nginx also terminates TLS, adds security headers, and enforces upload/rate limits at the edge — keeping the app process focused. | Serving the SPA from FastAPI (wastes worker capacity, muddles separation). | Low. |
| **Migrations run as an explicit deploy step** | Schema changes must be observable and ordered, not a side effect of an app boot that might run in several processes at once. | Auto-migrate on startup (race conditions across processes; silent surprises). | Low. |
| **Nightly `pg_dump` + off-box copy, restore documented and tested** *(new)* | Transcripts *are* the product's value — they cost real CPU minutes and can't be regenerated once source videos disappear. A single-VPS deployment with no backup is one disk failure from total data loss, and an untested backup is not a backup. | No backups (unacceptable); volume snapshots only (host-dependent, and untested restores). | Low. |
| **Disk/liveness alerting** *(new)* | The box runs unattended with a known disk-exhaustion failure mode (§6.7). Learning about a full disk from a user report is too late; a threshold alert makes it a five-minute fix. | Manual checking (won't happen reliably). | Low. |
| **Redis + ARQ, object storage, SSE — deferred, not designed out** | Each is a documented adapter swap behind an existing port. We add them when a real limit is hit, not on speculation — but the seams exist now, so adding them is never a rewrite. | Building them now (infrastructure and operational cost on a box that can't spare it, for load we don't have). | Low by design. |

---

## 11. Quality tooling

| What | Why | Instead of | Reversal cost |
|---|---|---|---|
| **Ruff (lint **and** format)** *(refinement)* | Ruff now covers formatting Black-compatibly, so one fast tool replaces two — fewer dependencies, one config, no formatter disagreements in CI. **This supersedes the earlier `black` + `ruff` plan;** output is materially the same. | black + ruff + isort (three tools, same result); flake8 stack (slower, plugin sprawl). | Trivial. |
| **mypy, strict, with narrow documented exceptions** | Strict typing is what makes Clean Architecture's boundaries checkable rather than aspirational. Untyped third-party libraries get per-module ignores **with a comment** — never a blanket relaxation. | Loose typing (boundaries decay silently); pyright (fine, but mypy has broader plugin support here). | Low. |
| **pytest (+ `pytest-asyncio`), fakes over mocks** | Domain and application tests run with fake port implementations — no I/O, no network, deterministic and fast. Real FFmpeg/whisper tests exist but are marked `slow` and run on tiny fixtures, so the everyday suite stays quick. | Heavy mocking (tests assert implementation details, not behavior); integration-only testing (slow, flaky, poor failure localization). | Low. |
| **Vitest + Testing Library + MSW** | Vitest shares Vite's transform pipeline (no second build config); Testing Library pushes tests toward user-visible behavior; MSW intercepts at the network layer so components are tested against the real contract shape. | Jest (separate toolchain config); mocking hooks directly (couples tests to implementation). | Low. |
| **ESLint (+ typescript-eslint, react-hooks, jsx-a11y) + Prettier** | `jsx-a11y` catches a meaningful share of accessibility regressions automatically — cheaper than manual audits against our AA target. | Manual review only (regressions slip through). | Trivial. |
| **Pre-commit hooks + CI re-running everything** | Hooks give fast local feedback; CI is the authority because hooks can be skipped. | CI only (slow feedback loops); hooks only (bypassable). | Trivial. |
| **Conventional Commits, protected `main`, small PRs** *(approved)* | Machine-readable history enables changelog/versioning later, and enforced review keeps the standards in `CODING_STANDARDS.md` from being optional. | Freeform commits (unparseable history). | Trivial. |

---

## 12. Resolved decisions (previously open)

| # | Question | Decision | Rationale |
|---|---|---|---|
| 1 | Refresh-token transport | **HttpOnly + Secure + SameSite=Lax cookie**, with CSRF double-submit on the two cookie endpoints | XSS cannot read the long-lived credential; CSRF risk is closed explicitly rather than assumed away (§5) |
| 2 | Future queue backend | **Redis + ARQ**, behind the existing `QueueService` | Async-native, far lighter than Celery, persistent queue (§6.1) |
| 3 | Batch/model defaults | **25 URLs/batch**, **`small` + int8**, **2h max duration — now enforced via pre-flight**, retry **in v1** | Matches real CPU-only throughput; limits are enforced, not merely documented (§6.5, §6.7, §7) |
| 4 | Admin visibility of transcript content | **Metadata only**; content access via an explicit, **audit-logged** support path | Operators get what they need without a standing right to read user content (§5) |
| 5 | Hostinger plan type | **Still the top blocker** — plus an added independent check: whether the host's IP range is blocked by the video source | Confirming root access isn't sufficient if the datacenter IP can't fetch videos (§13) |
| 6 | Per-item retry in the UI | **In v1** | Per-item failure is expected; resubmitting a whole batch to fix one URL is a poor experience (§6.5) |
| 7 | Transcript viewer layout | **Split-pane ≥`lg`, tabs below** | Reading and timestamp-scanning is a two-pane task on desktop only (§9) |
| 8 | Formatter / linter / commits | **Ruff (lint+format)**, **mypy strict**, **Conventional Commits** | One tool where two were planned; checkable boundaries; parseable history (§11) |
| 9 | Brand palette | **Zinc + indigo placeholder**, tokens only | Unblocks UI work; rebranding is a token edit (§9) |
| 10 | Cache derived export files | **No** — derive on demand | Disk is the scarce resource; formatting is effectively free (§7) |
| 11 | Soft vs hard delete | **Soft-delete user-facing rows**, purge children on hard delete via a cleanup task | Accidental job deletion is recoverable; disk is still reclaimable on a schedule |
| 12 | `progress_events` in v1 | **Table exists, writes off by default** | Keeps the future option without paying per-tick writes today (§4) |

---

## 12.1 Development environment: WSL2, not Windows-native *(discovered 2026-07-28)*

- **What:** all development runs inside **WSL2 / Ubuntu**. Windows-native Python and Node development is not viable on the owner's machine.
- **Why:** **Smart App Control is enforced** (`VerifiedAndReputablePolicyState = 1`), and it blocks unsigned compiled libraries. Confirmed empirically, not theorised:

  | Component | Result |
  |---|---|
  | `pydantic_core` (FastAPI/pydantic) | **Blocked** — the API cannot start |
  | `rollup` native module | **Blocked** — no frontend build, no tests, not even the dev server |
  | `ctranslate2` (Phase 2 transcription) | Would be blocked identically |
  | `npm install`, `tsc`, `eslint`, SQLAlchemy, structlog, esbuild | Work fine (pure Python/JS) |

  The block is on the *file*, not the location — reproduced on both `C:` and `E:`.
- **Instead of:** turning Smart App Control off (a genuine security downgrade, and **irreversible without reinstalling Windows** — so not a decision to make casually on a daily-use machine); or Docker Desktop (needs WSL2 anyway, plus ~2GB and less reliable hot reload while learning).
- **Bonus wins:** Ubuntu 24.04 ships **Python 3.12**, exactly the version we want, so no extra install. And development now happens on the same OS as production, which removes a whole class of "worked in dev" surprise.
- **Reversal cost:** none — Docker can be added on top of the same WSL2 later.
- **Practical caveat:** with the repo on a Windows drive (`/mnt/e/...`), file-change events do not cross reliably, so hot reload can silently stop. Fixed by `VITE_USE_POLLING=true`; if it becomes annoying, move the repo into the WSL filesystem.

---

## 13. Known risks this document does **not** resolve

1. **Hostinger plan type (blocker).** If it is shared/managed hosting, no amount of architecture helps — FFmpeg, yt-dlp, and whisper cannot run. Must be confirmed before Phase 5.
2. **Datacenter IP blocking by video sources (independent blocker).** Even a correct VPS can find its IP range blocked or bot-challenged by YouTube, which would cause widespread download failures **that look like our bug**. This must be tested from the actual production IP early — it can invalidate the local-download approach regardless of plan type. Documented fallbacks: cookie/PO-token support, a proxy, or switching `TranscriptionProvider` to a hosted API. This is why that port exists.
3. **Real CPU throughput on the target box** is unknown until benchmarked. It may force `base` as the default model or push transcription to an API. Recorded in Phase 5.
4. **Legal/ToS exposure** of downloading third-party video remains a product-level decision (acceptable-use terms), not a technical one.

---

> **Governance:** changing anything in this document requires updating the affected spec doc in the same PR. Decisions may be revisited — but they get revisited *here*, with a reason, not silently in code.
