# Coding Standards

Deliverable for step 9 of the development workflow.

These describe the conventions the codebase already follows. Where a rule exists
because of a specific problem, the reason is stated — a rule whose purpose is
forgotten gets broken.

---

## 1. Principles, in priority order

1. **Simplicity** — the least machinery that solves the problem
2. **Maintainability** — a colleague reads it in six months and understands it
3. **Scalability** — grows without a rewrite
4. **Extensibility** — new features attach, they do not require surgery
5. **Developer experience** — clone and run
6. **Performance** — fast enough, measured not guessed
7. **Security** — safe by construction, not by discipline

**Free and open source first.** No paid service enters the codebase where a
stable free alternative achieves the same result.

---

## 2. Folder structure

```
backend/app/
  api/            HTTP only — validation, serialisation, status codes
    routes/       One module per resource
    deps.py       Shared dependencies (session, current user)
    router.py     Assembly; auth applied once, here
  core/           Cross-cutting: errors, logging, security, text helpers
  db/             Models and session management
  platforms/      URL recognition, one module per platform
  services/       Business logic — the substance of the application
    transcription/  Provider registry
    export/         Format registry
  workers/        Queue and worker loop
  cli.py          Command-line admin tasks
  config.py       Settings, environment-driven
  diagnostics.py  System self-check

frontend/src/
  components/     Shared components
    ui/           shadcn primitives — owned, editable, never auto-updated
  pages/          One file per route
  lib/            API client, types, formatting, auth context
```

**The dependency rule, and it is not negotiable:** `api → services → db`.
`services` never imports `api`. `db` imports nothing above it. When a service
needs something from a request, it is passed in as an argument.

---

## 3. Naming

| Thing | Convention | Example |
|---|---|---|
| Python module | `snake_case` | `services/metadata.py` |
| Python class | `PascalCase` | `TranscriptionProvider` |
| Python function | `snake_case` | `fetch_metadata` |
| Private helper | Leading underscore | `_estimate_size` |
| Constant | `UPPER_SNAKE` | `MAX_AUDIO_BYTES` |
| React component | `PascalCase` file and export | `ExportMenu.tsx` |
| TS function | `camelCase` | `formatDuration` |
| Route path | lowercase, plural | `/api/transcripts` |
| Database table | lowercase, plural | `transcript_segments` |
| Env var | `UPPER_SNAKE` | `FASTER_WHISPER_MODEL` |

**Name things by what they mean to a user, not how they are implemented.** A
person manages *notifications*, not *webhook config*.

---

## 4. Python

**Style.** Ruff, line length 100. Enabled rules: `E`, `F`, `I`, `UP`, `B`, `SIM`.
`ruff check .` must pass before commit.

**Types.** Annotate every function signature. `from __future__ import
annotations` at the top of every module.

**Async.** The whole stack is async. Blocking work — yt-dlp, faster-whisper —
goes through `anyio.to_thread.run_sync` so the event loop keeps serving. A
blocking call on the event loop is a bug, not a style issue.

**Database sessions.** Short transactions. A session is never held open across a
download or a transcription — on SQLite that blocks every other writer.

**Docstrings.** Module-level docstrings explain *why the module exists*, not
what it contains. Function docstrings only where the name is insufficient.

**Comments.** Explain the non-obvious decision, never restate the code:

```python
# platform_video_id is intentionally not overwritten: it is the identity we
# de-duplicate on, and the provider's own id can differ (Instagram shortcode vs
# numeric media id) which would fork the row.
```

---

## 5. TypeScript / React

**Style.** ESLint with the TypeScript and React Hooks plugins. `npm run lint`
and `tsc --noEmit` must both pass.

**Types.** `strict: true`. No `any`. API types live in `lib/types.ts` and mirror
the backend schemas — one file to update when the contract changes.

**Components.** Function components with hooks. One component per file for
anything non-trivial. Props typed inline for small components, as a named
interface when reused.

**State.** Local `useState` by default. Context only for genuinely global state
(currently: authentication). No state library — the app does not need one.

**Data fetching.** Through `lib/api.ts`. No component calls `fetch` directly.
Every call can throw `ApiError`; every caller handles it and shows the message.

**Styling.** Tailwind utilities. Shared appearance goes into a `ui/` component,
not a copied class string.

---

## 6. Error handling

**Backend.** Every expected failure is an `AppError` subclass carrying a stable
machine-readable `code`, an HTTP `status_code`, and a `retryable` flag. One
exception handler converts them into a consistent body:

```json
{ "code": "video_unavailable", "message": "This video is unavailable — it may be private, deleted, or region-locked." }
```

**Messages are written for the person reading them.** Not `ERR_METADATA_502`.
Say what happened and what to do about it.

**`retryable` is a real decision, not a default.** A network timeout retries. A
private video does not, because it never will succeed and three identical
failures help nobody.

**Frontend.** Errors appear next to the thing that failed. Never a browser
`alert`. Never a bare status code.

---

## 7. Logging

Standard library `logging`, configured once. Levels used consistently:

| Level | For |
|---|---|
| `DEBUG` | Development detail |
| `INFO` | Normal lifecycle — job claimed, job finished |
| `WARNING` | Recovered or user-caused — job failed, stale job requeued |
| `ERROR` | Unexpected, with a stack trace |

**Never log a password, a token, or a full transcript.** Log ids and counts.

---

## 8. Testing

**Every test runs without network, ffmpeg, or API keys.** A suite that needs
credentials is a suite nobody runs. The media backend is faked and the
transcription provider is a stub.

**Test names are sentences that state the claim:**

```python
def test_video_over_the_duration_limit_never_downloads()
def test_wrong_password_and_unknown_email_give_the_same_answer()
```

Not `test_limits_2`.

**Test the behaviour, not the implementation.** Assert the over-limit video was
never downloaded — not that a particular function was called.

**Tests that need the real world are skipped, not deleted.** The real
transcription test skips when the model is absent, so a fresh clone stays green
while a prepared machine gets genuine proof.

---

## 9. Extension points

Adding any of these is **adding a file**, never editing a dispatch chain:

| To add | Do |
|---|---|
| A platform | Subclass `PlatformAdapter`, register in `platforms/__init__.py` |
| A transcription provider | Subclass `TranscriptionProvider`, register in `transcription/__init__.py` |
| An export format | Subclass `Exporter`, register in `export/__init__.py` |
| A search backend | Subclass `SearchBackend` |
| A pipeline stage | Add a method, append it to `Pipeline._STAGES` |

If a change requires editing an `if/elif` over types, the registry pattern was
bypassed and the change is wrong.

---

## 10. Security

- **Secrets from the environment only.** `.env` is gitignored; `.env.example`
  carries names, never values.
- **Passwords** bcrypt-hashed with a per-password salt.
- **Subprocesses** invoked with argument *lists*, never a shell string. No user
  input reaches a shell.
- **User-supplied text in filenames** is sanitised — it reaches
  `Content-Disposition` headers and ZIP entries.
- **URL validation before any fetch.** Only http and https, only registered
  platforms. This is the SSRF boundary.
- **Auth applied once** at the router, so a new route cannot ship unprotected.

---

## 11. Git

**Branches:** `claude/<topic>` or `feature/<topic>`. Never commit to `main`
directly.

**Commit messages:** a subject line saying what changed, then a body saying
*why*. The diff already shows what.

```
Fall back to the placeholder when a thumbnail fails to load

Platform thumbnail URLs expire and CDNs fail. The component only handled a
missing URL, not a present-but-broken one — so a dead link rendered as a
broken image icon with the alt text sprawling across the row.
```

**One logical change per commit.** Tests and lint pass before every commit.

**Pull requests** describe what changed, what was verified, and — importantly —
**what was not verified**. An honest limitations section is worth more than a
feature list.

---

## 12. Definition of done

A feature is done when:

- [ ] It matches its approved specification
- [ ] Tests cover the behaviour, including the failure paths
- [ ] `ruff check`, `tsc --noEmit` and `npm run lint` all pass
- [ ] Errors are in plain English with a next step
- [ ] Empty and loading states exist
- [ ] It works from 360 px wide, in light and dark
- [ ] Documentation is updated in the same commit
- [ ] Anything unverified is stated explicitly, not omitted
