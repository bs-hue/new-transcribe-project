# API reference

Interactive docs (generated from the code, always current):
**http://localhost:8000/docs**

All routes are under `/api` and require a bearer token, except `/api/health` and
`/api/auth/login`.

```bash
TOKEN=$(curl -s localhost:8000/api/auth/login \
  -H 'Content-Type: application/json' \
  -d '{"email":"you@agency.com","password":"…"}' | jq -r .access_token)

curl localhost:8000/api/videos -H "Authorization: Bearer $TOKEN"
```

Errors share one shape:

```json
{ "code": "unsupported_url", "message": "Unsupported URL. Supported platforms: YouTube, Instagram.", "details": {} }
```

---

## Authentication

| Method | Path | Purpose |
|---|---|---|
| `POST` | `/api/auth/login` | Exchange email + password for a token — **public** |
| `GET` | `/api/auth/me` | The signed-in user |
| `POST` | `/api/auth/me/password` | Change your own password (needs the current one) |
| `GET` | `/api/auth/users` | List accounts — **admin** |
| `POST` | `/api/auth/users` | Create an account — **admin** |
| `PATCH` | `/api/auth/users/{id}` | Change name, role, active state, password — **admin** |
| `DELETE` | `/api/auth/users/{id}` | Remove an account — **admin** |

Tokens last `ACCESS_TOKEN_EXPIRE_MINUTES` (12 hours by default) and cannot be
revoked before then — but every request re-checks the account, so deactivating
someone takes effect immediately.

Login returns the same message for an unknown email and a wrong password, so the
endpoint cannot be used to discover which addresses have accounts.

---

## Discovery

| Method | Path | Purpose |
|---|---|---|
| `GET` | `/api/health` | Liveness, database state, queue depth — **public** |
| `GET` | `/api/meta` | Platforms, export formats, limits, transcription readiness |

`/api/meta` is what the UI reads instead of hardcoding anything — add an export
format on the server and it appears in the dropdown.

---

## Submitting videos

### `POST /api/videos/preview`

Validate and probe **without downloading**. This is the step that lets a user
drop items from a batch before any transfer starts.

```json
{ "urls": ["https://youtu.be/dQw4w9WgXcQ", "https://vimeo.com/1"] }
```

`urls` also accepts a single newline- or comma-separated string.

```json
{
  "results": [
    {
      "url": "https://youtu.be/dQw4w9WgXcQ",
      "valid": true,
      "platform": "youtube",
      "title": "…", "author": "…", "thumbnail_url": "…",
      "duration_seconds": 212.0,
      "estimated_size_bytes": 18874368,
      "within_limits": true,
      "limit_reasons": [], "warnings": [],
      "already_transcribed": false
    },
    { "url": "https://vimeo.com/1", "valid": false, "error_code": "unsupported_url", "error_message": "…" }
  ]
}
```

### `POST /api/videos` → `202`

Queue a job per valid URL. One bad URL never fails the batch — every URL gets its
own verdict.

```json
{ "urls": ["…"], "language": "en" }
```

```json
{
  "batch_id": "5f2c…",
  "accepted_count": 2,
  "rejected_count": 1,
  "results": [{ "url": "…", "accepted": true, "job_id": "…", "video_id": "…", "duplicate_of_existing_video": false }]
}
```

---

## Tracking progress

| Method | Path | Purpose |
|---|---|---|
| `GET` | `/api/jobs/batch/{batch_id}` | Aggregate status for one submission — poll this |
| `GET` | `/api/jobs?status=&batch_id=&limit=&offset=` | List jobs |
| `GET` | `/api/jobs/{job_id}` | One job |
| `POST` | `/api/jobs/{job_id}/retry` | Requeue a failed or cancelled job |
| `POST` | `/api/jobs/{job_id}/cancel` | Cancel a job that has not started |

`stage` moves through `pending → fetching_metadata → checking_limits →
downloading → extracting_audio → transcribing → storing → done`, and `progress`
is `0.0–1.0` across the whole pipeline.

---

## Browsing

| Method | Path | Purpose |
|---|---|---|
| `GET` | `/api/videos?platform=&author=&has_transcript=&limit=&offset=` | List videos |
| `GET` | `/api/videos/{video_id}` | Video + latest transcript + segments + latest job |
| `DELETE` | `/api/videos/{video_id}` | Delete video, transcripts, and search entries |
| `GET` | `/api/transcripts?platform=&limit=&offset=` | List transcripts |
| `GET` | `/api/transcripts/{transcript_id}` | One transcript with segments |

---

## Search

### `GET /api/search`

`q` (required), plus optional `platform`, `author`, `created_after`,
`created_before`, `limit`, `offset`.

```json
{
  "query": "hook",
  "total": 1,
  "items": [
    {
      "transcript_id": "…", "video_id": "…",
      "snippet": "…Here is the hook framework we use…",
      "rank": 1.33e-6,
      "title": "…", "author": "…", "platform": "youtube", "word_count": 61
    }
  ]
}
```

Query text is treated as literal terms, never as search-engine syntax, so a
stray quote or `AND` returns results rather than an error.

---

## Export

### `GET /api/transcripts/{transcript_id}/export?format=`

`format` is one of `txt`, `docx`, `md`, `xlsx`, `json`, `srt`, `vtt`. Returns the
file with a `Content-Disposition` attachment header.

`srt` and `vtt` need timed segments; requesting them for a transcript without
segments returns `422 unsupported_export_format`.

### `POST /api/exports`

Bulk export. Select by ids, by video, by search query, or any combination.

```json
{ "format": "xlsx", "transcript_ids": [], "video_ids": ["…"], "query": "hook", "limit": 200 }
```

`xlsx` and `json` return a single combined file (one workbook, all rows — which
is the point of exporting to a spreadsheet). Every other format returns a ZIP,
with duplicate titles disambiguated.
