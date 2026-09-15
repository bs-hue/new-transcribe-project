# Module: `transcription`

**Status:** not implemented — Phase 2.

The core module: turn submitted URLs into stored transcripts, reliably, on a small
CPU-only server.

## Planned layers

| Layer | Contents |
|---|---|
| `domain/` | `Job`, `JobItem`, `Transcript`, `Segment`, `Summary`; the item state machine; retryable-vs-terminal error classification; lease rules; export formatters (pure functions) |
| `application/` | `CreateBatchJob`, `RunJobItem` (the pipeline orchestrator), `GetJob`, `ListJobs`, `GetJobProgress`, `CancelJob`, `RetryJobItem`, `DeleteJob`, `GetTranscript` |
| `infrastructure/` | yt-dlp and FFmpeg subprocess adapters, faster-whisper provider, LLM provider, background-task queue, polling progress, SQLAlchemy repositories |
| `interface/` | `/jobs/*` and `/transcripts/*` routers and schemas |

## Pipeline (per item)

```
pre-flight (metadata only) → download → extract audio → transcribe
  → summarize (optional) → save transcript → delete media
```

## Non-obvious requirements — read before implementing

- **Pre-flight first.** `yt-dlp --dump-json` resolves duration, live status, and
  playlist detection *before* downloading. Rejects playlists, live streams, and
  over-long videos as terminal failures.
- **Disk guard.** Require `MIN_FREE_DISK_MB` before downloading; a full disk takes
  down Postgres and the entire application.
- **Cleanup in `finally`.** Temp media is deleted on success, failure, timeout,
  and cancellation. Failure is the common case where files leak.
- **CPU isolation.** yt-dlp and FFmpeg are subprocesses; whisper runs in a
  `ProcessPoolExecutor`. Never a thread pool — the GIL would starve the API.
- **Leases.** Claim an item with `lease_owner`/`lease_expires_at`, renewed on each
  progress update. A reaper requeues items whose lease expired.
- **Per-stage timeouts.** With concurrency of 1, an unbounded stage stalls the
  whole system.
- **Cooperative cancellation.** Kill subprocesses immediately; check the cancel
  flag between transcription segments.

Full detail: `docs/TECHNICAL_ARCHITECTURE.md` §4.4-4.8.
