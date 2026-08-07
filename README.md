# Content Research Hub

An internal AI research hub for the content team. Paste YouTube or Instagram Reel
URLs, and the system collects, transcribes, stores, searches and exports the
research — so writers and strategists spend their time creating instead of
gathering.

> **Status: Version 1** — the transcription and research-collection workflow.
> The architecture is deliberately modular so V2 (AI analysis of transcripts) and
> V3 (cross-creator research, generation) plug in without rewriting V1.

**Runs on free, open-source software end to end.** No paid API, no licence fee,
no SaaS subscription. Transcription runs locally. The only cost is the server.
Every dependency is justified against alternatives in
[`docs/TECH_STACK.md`](docs/TECH_STACK.md).

---

## What Version 1 does

| # | Capability |
|---|---|
| 1 | Validate every submitted URL |
| 2 | Reject unsupported URLs with a clear reason |
| 3 | Fetch metadata *before* downloading (title, thumbnail, duration, estimated size, platform, author) |
| 4 | Check the video against configured system limits |
| 5 | Download the video |
| 6 | Extract audio |
| 7 | Generate accurate transcripts locally (segment-level, with timestamps) |
| 8 | Store transcripts in the database |
| 9 | Search across every previous transcript |
| 10 | Export to TXT, DOCX, Markdown, XLSX, JSON, SRT, VTT (single or bulk ZIP) |

Plus sign-in with JWT, and admin-managed team accounts.

---

## Stack

| Layer | Choice |
|---|---|
| Backend | Python 3.11 · FastAPI · SQLAlchemy |
| Frontend | React · TypeScript · Vite · Tailwind CSS · shadcn/ui |
| Database | SQLite (development) → PostgreSQL (production) |
| Downloading | yt-dlp |
| Audio | FFmpeg |
| Speech-to-text | faster-whisper — **local and free** |
| Auth | JWT (PyJWT + bcrypt) |
| Storage | Local filesystem |
| Deployment | Docker · Docker Compose · Linux VPS |

---

## Quick start

> **Setting this up for the first time, or not a developer?** Start with
> [`docs/SETUP.md`](docs/SETUP.md) — a step-by-step guide in plain language,
> including what to do when something breaks. The rest of this section is the
> short version for developers.
>
> **Opening it in an editor** (Antigravity, VS Code, Cursor, Windsurf)? See
> [`docs/OPEN-IN-EDITOR.md`](docs/OPEN-IN-EDITOR.md). The project ships with
> `.vscode/` tasks, so install, check and run are menu items rather than
> commands to memorise.

### With Docker (recommended)

```bash
cp .env.example .env
# Set BOOTSTRAP_ADMIN_EMAIL and BOOTSTRAP_ADMIN_PASSWORD to create the first
# account, and JWT_SECRET if this is not a throwaway environment.
docker compose up --build
```

- App: http://localhost:3000
- API docs: http://localhost:8000/docs

### Without Docker

Requirements: **Python 3.11+**, **Node 20+**, **ffmpeg** on `PATH`.

```bash
# Backend
cd backend
python -m venv .venv && source .venv/bin/activate
pip install -e ".[dev]"
cp ../.env.example ../.env
python -m app.cli create-user --email you@agency.com --admin   # first account
uvicorn app.main:app --reload --port 8000

# Frontend (second terminal)
cd frontend
npm install
npm run dev          # http://localhost:5173
```

---

## Transcription

Runs on your own machine. Free, offline, and no audio ever leaves your network.
**There is no paid option in the codebase** — no API key setting exists, so no
configuration mistake can incur a charge.

| Provider | `TRANSCRIPTION_PROVIDER` | Notes |
|---|---|---|
| **faster-whisper** (default) | `faster_whisper` | Free, local, no API key. Set `FASTER_WHISPER_MODEL` (`tiny`/`base`/`small`/`medium`/`large-v3`). Bigger is more accurate and slower. |
| Stub | `stub` | Deterministic fake output, for tests and UI work. |

Speed depends on your hardware — see
[`docs/SETUP.md`](docs/SETUP.md#about-transcription-speed) for the accuracy/speed
dial and how to tune it. Adding a provider is one file, should a better free one
appear — see [`docs/TECHNICAL_ARCHITECTURE.md`](docs/TECHNICAL_ARCHITECTURE.md#adding-a-transcription-provider).

---

## Command line

```bash
# Check this machine can run the hub. --deep downloads the speech model and
# transcribes a bundled clip, proving the whole audio → text chain and
# reporting how fast transcription is on this hardware.
python -m app.cli doctor --deep

python -m app.cli create-user --email you@agency.com --admin
python -m app.cli list-users
python -m app.cli reset-password --email you@agency.com
```

Under Docker, prefix with `docker compose exec api`.

Omit `--password` to be prompted, so it never lands in shell history. Admins can
also manage the team from the **Team** page in the UI.

---

## Configuration

Environment-driven; see [`.env.example`](.env.example) for the commented list.
The settings people actually change:

| Variable | Default | Meaning |
|---|---|---|
| `JWT_SECRET` | *(insecure default)* | **Required in production** — the app refuses to start otherwise |
| `TRANSCRIPTION_PROVIDER` | `faster_whisper` | See above |
| `FASTER_WHISPER_MODEL` | `base` | Accuracy vs speed |
| `DATABASE_URL` | SQLite file | Swap for `postgresql+asyncpg://…` in production |
| `MAX_VIDEO_DURATION_SECONDS` | `7200` | Reject longer videos at the limits stage |
| `WORKER_CONCURRENCY` | `2` | Videos processed in parallel |

---

## Project layout

```
backend/     FastAPI service — pipeline, storage, search, exports, auth
frontend/    React + Vite UI — submit, review, search, export, team
docs/        The 8 workflow deliverables, plus SETUP · DEPLOYMENT · SUPABASE · COOKIES
.vscode/     Shared editor tasks — install, check, run, test
scripts/     Operational scripts — database and certificate backups
```

Putting this on a server for other people to use:
[`docs/DEPLOYMENT.md`](docs/DEPLOYMENT.md).

Design rationale and V2/V3 extension points:
[`docs/TECHNICAL_ARCHITECTURE.md`](docs/TECHNICAL_ARCHITECTURE.md).

---

## Tests

```bash
cd backend && pytest        # 144 tests
cd frontend && npm run build && npm run lint
```

The backend suite covers URL validation, limits, exports, search, authentication,
diagnostics and the full pipeline — using the `stub` transcription provider and a
fake media backend, so it runs without network access, ffmpeg, or API keys.

One test performs a **real** local transcription of a bundled speech clip. It
skips automatically when the model has not been downloaded, so a fresh clone
stays green — but once you have run `doctor --deep`, it proves free local
transcription genuinely works on your machine.
