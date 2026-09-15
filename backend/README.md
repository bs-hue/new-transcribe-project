# Backend

FastAPI application following Clean Architecture. See
[`docs/TECHNICAL_ARCHITECTURE.md`](../docs/TECHNICAL_ARCHITECTURE.md) for the full design.

## Layout

```
app/
├─ main.py            Composition root — the only file that picks concrete implementations
├─ core/              Framework-aware plumbing
│  ├─ config.py       Every setting, typed and validated at startup
│  ├─ logging.py      Structured logging with correlation IDs
│  ├─ errors.py       Domain errors -> HTTP error envelope
│  ├─ middleware.py   Correlation IDs and request logging
│  ├─ database.py     Engine, sessions, Unit of Work adapter
│  ├─ clock.py        System clock adapter
│  └─ dependencies.py Shared FastAPI dependencies
├─ shared/            Shared kernel — pure, no framework imports allowed
│  ├─ domain/         Entity, pagination, error vocabulary
│  └─ ports/          Interfaces: Clock, UnitOfWork (more arrive in Phase 2)
├─ platform/          /health and /config/public (not a bounded context)
└─ modules/           Bounded contexts
   ├─ auth/           Phase 1
   └─ transcription/  Phase 2
migrations/           Alembic revisions
tests/                Mirrors the app structure
```

## The dependency rule

```
interface  ->  application  ->  domain
                                  ^
infrastructure ────────────────────┘  (implements domain ports)
```

The **domain imports nothing** from other layers and no framework. If you find
yourself adding `from fastapi import ...` to a domain file, the logic belongs
somewhere else.

## Running

From the repository root, `.\scripts\dev-backend.ps1`. Or manually:

```powershell
.venv\Scripts\python.exe -m uvicorn app.main:app --reload
```

- Health: <http://localhost:8000/api/v1/health>
- Interactive docs (development only): <http://localhost:8000/api/v1/docs>

## Checks

```powershell
.venv\Scripts\ruff check .            # lint
.venv\Scripts\ruff format .           # format
.venv\Scripts\mypy app                # types (strict)
.venv\Scripts\pytest                  # tests
```

Slow tests that need real FFmpeg or whisper are marked `slow` and excluded by
default. Run them with `pytest -m slow`.

## Migrations

```powershell
.venv\Scripts\alembic upgrade head                       # apply
.venv\Scripts\alembic revision -m "add users table"      # new empty revision
.venv\Scripts\alembic revision --autogenerate -m "..."   # draft from models
```

Autogenerate produces a **draft**. Read it before committing — and remember that
new model modules must be imported in `migrations/env.py`, or Alembic cannot see
them.
