# Feature: `transcription`

**Status:** not implemented — Phase 3.

The screens users actually come for: submit URLs, watch progress, read and
download transcripts.

## Planned contents

- `pages/NewJobPage.tsx` — multi-URL input with per-URL validation, options panel
- `pages/JobsPage.tsx` — dashboard list with status filters and pagination
- `pages/JobDetailPage.tsx` — per-item live progress, cancel, retry
- `pages/TranscriptPage.tsx` — reading and segment views, downloads, summary panel
- `components/` — `UrlBatchInput`, `StatusBadge`, `StageProgress`, `JobItemCard`,
  `SegmentList`, `DownloadMenu`
- `api/` — typed hooks for `/jobs/*` and `/transcripts/*`

## Requirements that are easy to get wrong

- **Poll only while it matters.** Progress polling runs only while at least one
  item is non-terminal *and* the tab is focused, with mild backoff. Constant
  polling from several open tabs is real load on a one-job-at-a-time server.
- **Read limits from the server.** `max_urls_per_batch`, `max_video_duration_seconds`,
  and `available_models` come from `/config/public` — never hardcoded, so tuning
  the server needs no frontend release.
- **Retry only when it can work.** Show the retry action only when
  `error.retryable` is true. Offering a retry on a private or deleted video is
  worse than offering none.
- **A pending automatic retry is not a dead item.** Show "Retrying shortly
  (attempt 2 of 3)", not a bare "Failed".
- **Transcript viewer:** split-pane at `lg` and above, tabs below.

See `docs/UI_UX_SPECIFICATION.md` §3 and `docs/API_SPECIFICATION.md` §4-5.
