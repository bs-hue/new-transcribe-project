# Database Design

Deliverable for step 5 of the development workflow.

**SQLite** for development, **PostgreSQL** for production. No SQLite-specific
column types are used, so the switch is one setting (`DATABASE_URL`) and no code
change. Full-text search is the one genuine difference between the two and is
abstracted behind a search backend interface.

---

## 1. Entity relationship

```
                    ┌──────────┐
                    │  users   │
                    └────┬─────┘
                         │ submitted_by
                         ▼
┌──────────┐  1     N ┌──────────┐  N     1 ┌──────────┐
│  videos  │─────────>│   jobs   │<─────────│  users   │
└────┬─────┘          └────┬─────┘          └──────────┘
     │ 1                   │ 1
     │                     │
     │ N                   │ N
┌────▼────────┐       ┌────▼─────┐
│ transcripts │       │   logs   │
└────┬────────┘       └──────────┘
     │ 1
     │ N
┌────▼──────────────┐     ┌──────────┐
│ transcript_       │     │ exports  │
│ segments          │     └──────────┘
└───────────────────┘
```

**The shape that matters:** a *video* is the source content, a *job* is one
attempt to process it, and a *transcript* is the durable result. One video can
have many jobs (retries) and many transcripts (re-transcribed with a better
model). Nothing is overwritten.

---

## 2. Tables

### 2.1 `users` — built

| Column | Type | Notes |
|---|---|---|
| `id` | String(32) PK | UUID hex |
| `email` | String(255) UNIQUE, indexed | Stored lower-cased |
| `full_name` | String(255) NULL | |
| `hashed_password` | String(128) | bcrypt. Plaintext never stored or logged |
| `role` | String(16) | `admin` \| `member` |
| `is_active` | Boolean | Re-checked every request, so deactivation is immediate |
| `created_at` | DateTime(tz) | |
| `last_login_at` | DateTime(tz) NULL | |

Deliberately small. An internal tool needs "who are you" and "may you manage
accounts", not a permissions matrix. Roles can grow into one without moving data.

---

### 2.2 `videos` — built

One row per unique platform video.

| Column | Type | Notes |
|---|---|---|
| `id` | String(32) PK | |
| `platform` | String(32), indexed | `youtube` \| `instagram` |
| `platform_video_id` | String(128) | The id parsed from the URL |
| `source_url` | Text | Exactly as pasted |
| `canonical_url` | Text | Normalised form |
| `title`, `description` | Text NULL | From metadata |
| `author`, `author_url` | String/Text NULL | Creator, indexed on author |
| `thumbnail_url` | Text NULL | |
| `duration_seconds` | Float NULL | |
| `estimated_size_bytes` | Integer NULL | |
| `view_count`, `like_count` | Integer NULL | |
| `published_at` | DateTime(tz) NULL | |
| `raw_metadata` | JSON NULL | Trimmed provider payload |
| `created_at`, `updated_at` | DateTime(tz) | |

**`UNIQUE (platform, platform_video_id)`** — this is what stops the same video
being transcribed twice. It keys on the id parsed from the URL, not the
provider's own id, because those differ (Instagram shortcode vs numeric media
id) and would fork the row.

**`raw_metadata`** keeps fields V1 never modelled — hashtags, engagement,
categories — so V2 and V3 can mine them without re-downloading anything. It is
trimmed, not the full payload, which runs to hundreds of kilobytes per video.

---

### 2.3 `jobs` — built

One run of the pipeline for one video. **Also the queue.**

| Column | Type | Notes |
|---|---|---|
| `id` | String(32) PK | |
| `video_id` | FK → videos, CASCADE, indexed | |
| `batch_id` | String(32) NULL, indexed | Groups one submission |
| `submitted_by` | FK → users, SET NULL | **To add** — see §4 |
| `status` | String(16), indexed | `queued` \| `running` \| `completed` \| `failed` \| `cancelled` |
| `stage` | String(32) | `pending` → `fetching_metadata` → `checking_limits` → `downloading` → `extracting_audio` → `transcribing` → `storing` → `done` |
| `progress` | Float | 0.0–1.0 across the whole pipeline |
| `attempts` | Integer | |
| `error_code`, `error_message` | String/Text NULL | Machine-readable code plus plain English |
| `language` | String(16) NULL | Per-job override |
| `created_at`, `started_at`, `finished_at` | DateTime(tz) | |
| `heartbeat_at` | DateTime(tz) NULL | Stale detection — a crashed worker's job is requeued |

**Indexes:** `(status, created_at)` for claiming the oldest queued job;
`batch_id` for the batch view.

**Why the queue is a table.** Jobs are claimed with a conditional
`UPDATE … WHERE status = 'queued'`, atomic on both SQLite and Postgres. No
broker to operate. The interface is narrow enough to swap for Redis or SQS when
volume justifies it.

---

### 2.4 `transcripts` — built

| Column | Type | Notes |
|---|---|---|
| `id` | String(32) PK | |
| `video_id` | FK → videos, CASCADE, indexed | |
| `job_id` | String(32) NULL | Which run produced it |
| `text` | Text | Full transcript |
| `language` | String(16) NULL | Detected or forced |
| `provider`, `model` | String | e.g. `faster_whisper`, `base` |
| `word_count` | Integer | |
| `duration_seconds` | Float NULL | |
| `created_at` | DateTime(tz) | |

**Versioned, not overwritten.** Re-transcribing with a better model adds a row.
The API returns the newest by default. This is why upgrading the model later
does not destroy prior research.

---

### 2.5 `transcript_segments` — built

| Column | Type | Notes |
|---|---|---|
| `id` | String(32) PK | |
| `transcript_id` | FK → transcripts, CASCADE, indexed | |
| `index` | Integer | Order within the transcript |
| `start`, `end` | Float | Seconds |
| `text` | Text | |
| `speaker` | String(64) NULL | Unused in V1; reserved for diarisation |

Segments are what make SRT and VTT export real rather than approximated, and
what a future "jump to this quote in the video" feature needs.

---

### 2.6 `exports` — **to be added**

Specified in the plan, not yet built. Its purpose is an audit trail: who took
what out of the system, in what format, when.

| Column | Type | Notes |
|---|---|---|
| `id` | String(32) PK | |
| `user_id` | FK → users, SET NULL | Who exported |
| `format` | String(16) | `txt` \| `docx` \| `md` \| `xlsx` \| `json` \| `srt` \| `vtt` |
| `transcript_ids` | JSON | What was included |
| `transcript_count` | Integer | Denormalised, for cheap reporting |
| `query` | Text NULL | Set when exporting search results |
| `filename` | String(255) | What was delivered |
| `size_bytes` | Integer | |
| `created_at` | DateTime(tz), indexed | |

**Deliberately does not store the file.** Exports are cheap to regenerate from
transcripts, and storing them would grow without bound. This records the event,
not the artefact.

---

### 2.7 `logs` — **to be added**

Specified in the plan, not yet built. Application logs go to stdout, which is
right for operations, but does not survive a restart or answer "what happened to
this job three days ago?".

| Column | Type | Notes |
|---|---|---|
| `id` | String(32) PK | |
| `job_id` | FK → jobs, CASCADE, indexed NULL | Set for pipeline events |
| `user_id` | FK → users, SET NULL | Set for user actions |
| `level` | String(16) | `info` \| `warning` \| `error` |
| `event` | String(64) | e.g. `job.stage_changed`, `auth.login_failed` |
| `message` | Text | Human-readable |
| `context` | JSON NULL | Stage, error code, timings |
| `created_at` | DateTime(tz), indexed | |

**Scope discipline:** this is an *event* log for things a person may need to
review, not a firehose of debug output. Debug stays on stdout.

**Retention:** rows older than 90 days are deleted by a scheduled task. Without
that, this table becomes the largest in the database and the least useful.

---

## 3. Search index

**SQLite** — an FTS5 virtual table `transcript_fts (transcript_id UNINDEXED,
video_id UNINDEXED, title, author, body)` with the `porter unicode61` tokenizer,
kept in sync on write. Gives ranked results and snippet highlighting.

**PostgreSQL** — to be a `tsvector` column with a GIN index, behind the same
interface.

**Anything else** — a portable `LIKE` backend, correct everywhere, adequate to
five figures of transcripts.

User input never reaches the query parser as syntax; every term is re-quoted as
a literal phrase, so a stray quote returns results rather than an error.

**V3 note:** semantic search adds a fourth backend (embeddings) behind the same
single-method interface. Callers never learn which one they got.

---

## 4. Changes required

| Change | Reason | Migration |
|---|---|---|
| Add `jobs.submitted_by` | Dashboard and Job Details need to show who submitted a batch | Nullable column; existing rows stay NULL |
| Add `exports` table | Audit trail, specified in the plan | New table |
| Add `logs` table | Reviewable history, specified in the plan | New table |
| Add PostgreSQL `tsvector` search backend | Production search | New backend class, no schema change to existing tables |

All four are additive. No existing column changes type or meaning, so no data
migration is needed — only new structures.

---

## 5. Migrations

V1 creates tables with SQLAlchemy `create_all`: one schema version, no
production data. **That stops being adequate the moment this is deployed with
real data in it.**

**Before the first production deployment, adopt Alembic.** The models are
already structured for it. The changes in §4 are the natural first migration.

---

## 6. Scalability notes

| Concern | Position |
|---|---|
| SQLite write concurrency | One writer at a time. WAL mode lets reads continue during writes. Fine for two workers; move to Postgres for a busy multi-user deployment. |
| Transcript table growth | A transcript is a few kilobytes. 100,000 of them is well under a gigabyte. Not a concern. |
| Segment table growth | ~50 rows per transcript. Indexed on `(transcript_id, index)`. Fine into the millions. |
| `logs` growth | The one table that grows unboundedly. Hence the retention policy. |
| Media files | Not stored. Deleted immediately after transcription. |
