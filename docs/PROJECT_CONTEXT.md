# Project Context & Handoff

**Product:** AI Content Research Platform — Module 1: Bulk Transcript Agent
**Purpose of this file:** portable, committed context so **any** Claude Code account (or teammate) opening this repo inherits the project's scope, constraints, and decisions without relying on account-local memory.
**Status:** Specs **approved**; all design decisions resolved. No application code yet — next step is **Phase 0a (feasibility spike)**, then Phase 0 scaffolding.
**Last updated:** 2026-07-28

---

## 1. What this project is

Module 1 of a larger **AI Content Research Platform**. It ingests **online video URLs (YouTube etc.) in bulk** and produces transcripts:

```
URLs → yt-dlp (download) → FFmpeg (audio) → faster-whisper (STT)
     → optional LLM summary → exports (TXT / SRT / VTT / JSON, single + bulk zip)
```

Bulk transcription is deliberately the **first module** of a modular platform, so the ingest→process→store→deliver pipeline and infrastructure (auth, jobs, storage) are reused by future modules (Insights, Semantic Search/RAG, Translation, Competitor/Trend research).

## 2. Tech stack

- **Backend:** Python 3.11+, FastAPI, Uvicorn, SQLAlchemy 2.x + Alembic. Clean Architecture, modular bounded contexts.
- **Frontend:** React + TypeScript + Vite + Tailwind CSS + shadcn/ui (fully separated from backend).
- **DB:** SQLite (dev) → PostgreSQL (prod).
- **Media/STT:** yt-dlp, FFmpeg, faster-whisper.
- **Packaging:** Docker + Docker Compose.

## 3. Approved architecture decisions (2026-07-28)

- **Clean Architecture**, strict inward dependencies; ports in domain, adapters in infrastructure; composition root in `main.py`.
- **`QueueService` interface** — v1 uses FastAPI **BackgroundTasks**; Redis + **ARQ** can be added later with **no business-logic change**.
- **`ProgressService` interface** — v1 uses **DB-backed polling**; SSE / WebSockets later behind the same interface.
- **Auth from day one** — **JWT access + refresh tokens + RBAC**, multi-user, per-user data isolation.
- **`TranscriptionProvider` interface** — faster-whisper (CPU + int8) in v1, GPU-ready.
- **`LLMProvider` interface** — summaries are **optional, disabled by default, external API only** (no local LLM).

### 3.1 Reliability & security decisions added after architecture review (2026-07-28)

- **CPU isolation:** whisper runs in a `ProcessPoolExecutor`; yt-dlp/FFmpeg run as subprocesses. **Single uvicorn worker** in v1 (in-process queue/semaphore/rate-limit state).
- **Crash recovery:** items claimed under a **renewable lease**; a reaper requeues items whose lease expires.
- **Per-stage timeouts** — an unbounded stage is a system-wide stall when concurrency is 1.
- **Retry policy:** errors classified **retryable vs terminal**; auto-retry with backoff (3 attempts) + manual per-item retry in v1.
- **Cooperative cancellation:** subprocesses killed immediately; transcription aborts at the next **segment boundary**.
- **Disk guard:** pre-flight `--dump-json` metadata probe (duration/live/playlist), free-space headroom requirement, temp cleanup in `finally` on **all** paths. Playlist/channel URLs rejected.
- **Auth transport:** refresh token in an **HttpOnly/Secure/SameSite=Lax cookie** + **CSRF double-submit** on `/auth/refresh` and `/auth/logout`; access token in memory only. **argon2-cffi** and **PyJWT** (not passlib, not python-jose).
- **Admin scope:** metadata only; transcript-content access is audit-logged (`audit_logs`).
- **Ops baseline:** nightly off-box `pg_dump` with a **tested restore**, plus disk/liveness alerting.

## 4. Hard constraints (non-obvious — read before designing/deploying)

- **Production host:** a **Hostinger ₹699 plan whose type is UNCONFIRMED**. It **must be a VPS/KVM with root access** (to install FFmpeg, yt-dlp, Python, workers). **Shared/managed web hosting cannot run this stack.** Confirm the plan type **before any production deploy**.
- **Download viability from the production IP — a second, independent blocker.** Hosting-provider IP ranges are frequently bot-challenged or blocked by YouTube. This works perfectly in local dev and fails in production, where it looks like an application bug. **Test from the real IP in Phase 0a.** Fallbacks: cookies/PO-token, egress proxy, or swap `TranscriptionProvider` for a hosted STT API.
- **No GPU + limited RAM** in production → faster-whisper runs **CPU + int8**, concurrency capped at ~**1–2** simultaneous transcriptions, default model ~`small` (configurable). Interface keeps GPU/API swap trivial.
- **Small disk** → downloaded media (video/audio/temp WAV) is **deleted immediately after transcription**; only transcripts/summaries persist. Export files (SRT/VTT/TXT/JSON) are **derived on demand**, not stored.
- **Development happens in WSL2/Linux, not Windows-natively.** The owner's Windows 11 machine has **Smart App Control enforced**, which blocks unsigned compiled libraries. Verified blocked: `pydantic_core` (so the API cannot start) and `rollup`'s native module (so the frontend cannot build, test, or even run its dev server). `ctranslate2` would be blocked identically at Phase 2. Pure-Python and pure-JS tooling (`npm install`, `tsc`, `eslint`, SQLAlchemy, structlog) works fine. This is a Windows security policy — not fixable in code — and turning it off is **irreversible without reinstalling Windows**. WSL2 sidesteps it entirely and matches the production Linux target.
- **API never blocks** — all heavy work runs off the request path.

## 5. Working mode / conventions

- **Owner = product owner; Claude = technical architect.** Documentation-first: specs are approved before code.
- **No application code** until the owner approves the specs.
- Root rules file is **`CLAUDE.md.txt`** (note the `.txt` extension — rename to `CLAUDE.md` if you want the harness to auto-load it).

## 6. Source-of-truth documents (in `docs/`)

| File | Contents |
|---|---|
| `PRODUCT_REQUIREMENTS.md` | Vision, personas, FR/NFR, risks, open questions |
| `TECHNICAL_ARCHITECTURE.md` | Clean Architecture layers, module structure, all port interfaces, flows, deployment |
| `API_SPECIFICATION.md` | `/api/v1` REST contract (auth, jobs, transcripts, exports, progress), error envelope |
| `DATABASE_DESIGN.md` | Schema, ERD, SQLite↔Postgres portability, retention, migrations |
| `DEVELOPMENT_ROADMAP.md` | Phases 0–6+, each a vertical slice with Definition of Done |
| `UI_UX_SPECIFICATION.md` | Screens, flows, shadcn component inventory, states, a11y, responsiveness |
| `CODING_STANDARDS.md` | Clean Architecture enforcement, Python + TS standards, tooling, git, DoD |
| **`TECHNOLOGY_DECISIONS.md`** | **Every technology and pattern: why chosen, alternatives rejected, reversal cost. Governs all of the above.** |
| **`PLAIN_ENGLISH_GUIDE.md`** | **The same system with no assumed knowledge — for the owner, and for onboarding anyone non-technical. Start here.** |

## 7. Decisions — resolved 2026-07-28

| Question | Decision |
|---|---|
| Refresh-token transport | **HttpOnly/Secure/SameSite=Lax cookie** + CSRF double-submit on the two cookie endpoints |
| Future queue backend | **Redis + ARQ**, behind the existing `QueueService` |
| Batch / model defaults | **25 URLs**, **`small`+int8**, **2h max duration (enforced)**, retry **in v1** |
| Admin visibility | **Metadata only**; content access via an explicit, **audit-logged** path |
| Formatter / linter | **Ruff for lint *and* format** (supersedes black), **mypy strict**, Conventional Commits |
| Viewer layout / palette | **Split-pane ≥`lg`, tabs below**; **zinc + indigo** placeholder tokens |
| Export file caching | **No** — derived on demand; disk is the scarce resource |
| `progress_events` in v1 | Table ships, **writes off by default** |

Full rationale, alternatives rejected, and reversal cost for each: **`TECHNOLOGY_DECISIONS.md`**.

## 8. Remaining true blockers (not resolvable by design)

1. **Hostinger plan type** — VPS/KVM with root, or the processing stack cannot run at all.
2. **Download viability from the production IP** — independent of #1.
3. **Real CPU throughput on the box** — unknown until benchmarked; may force a smaller default model or a hosted STT API.

All three are probed in **Phase 0a**, before any application code is written.
