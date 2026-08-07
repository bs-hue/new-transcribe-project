# Product Requirements

Deliverable for step 2 of the development workflow.

---

## 1. The business problem

Account managers, content writers, strategists and the creative team research
hundreds of Instagram Reels and YouTube videos before writing anything. Today
that means: find the video, watch it, download it, transcribe it, read it,
identify the hook, the storytelling pattern, the CTA and the angle, take notes,
organise the notes, and only then start writing.

One research session takes several hours. As client count grows, this does not
scale.

**The problem is not transcription.** The problem is that collecting information
takes longer than creating the content it feeds. The team's creativity is spent
on clerical work.

### What success looks like

| Measure | Today | Target |
|---|---|---|
| Time to research 10 videos | 3–4 hours | Under 20 minutes of human attention |
| Where a transcript lives | Someone's laptop | One searchable library |
| Finding a phrase across past research | Not possible | Seconds |
| Cost per video researched | Staff time | Staff time, minus the clerical hours |

The measurable outcome is **hours returned to the team per week**, not
transcripts produced.

---

## 2. Users

| Role | What they do here | Frequency |
|---|---|---|
| Content Writer | Read transcripts, export to Word, search past research | Daily |
| Copywriter | Same, plus lifting hooks and phrasing | Daily |
| Creative Strategist | Compare creators, spot patterns across many transcripts | Weekly |
| Account Manager | Submit batches for a client, check they finished | Weekly |
| Performance Marketer | Search for offers and CTAs that performed | Occasional |
| Social Media Manager | Submit Reels, read transcripts | Daily |
| Administrator | All of the above, plus accounts and system settings | As needed |

**Two roles in the system:** `member` and `admin`. Members do research; admins
also manage accounts and settings. A finer permission model is not justified for
an internal tool of this size and is explicitly out of scope for V1.

**Non-negotiable:** every user is non-technical. No terminal, no configuration
files, no jargon without explanation.

---

## 3. Scope — Version 1

### In scope

| # | Requirement | Acceptance |
|---|---|---|
| R1 | Accept one or many URLs at once | Paste 20 links, all processed |
| R2 | Validate every URL | YouTube and Instagram accepted in all common link forms |
| R3 | Reject unsupported URLs with a reason | A Vimeo link is refused, naming the supported platforms |
| R4 | Fetch metadata before downloading | Title, thumbnail, duration, estimated size and platform shown with nothing transferred |
| R5 | Check against system limits | Over-length, over-size and live videos refused before download, each stating why |
| R6 | Download the video | Both platforms, with progress reported |
| R7 | Extract audio | 16 kHz mono, the format speech models expect |
| R8 | Generate accurate transcripts | Segment-level with timestamps |
| R9 | Store transcripts | Survives restart; re-transcribing adds a version rather than overwriting |
| R10 | Search previous transcripts | Phrase search across all, with surrounding context |
| R11 | Export | TXT, DOCX, Markdown, XLSX, JSON, SRT, VTT — individually and in bulk |
| R12 | Authentication | JWT sign-in; admin-managed accounts |

### Out of scope for V1

Any AI interpretation of transcripts (V2), cross-creator comparison and
generation (V3), platforms beyond YouTube and Instagram, mobile apps, client-
facing access, billing, and SSO.

### Constraints

- **No paid APIs.** V1 runs entirely on free, open-source software. There is no
  API-key setting in the codebase, so no misconfiguration can produce a bill.
- **Self-hosted.** Runs on a machine the agency controls. No client research
  leaves the network.
- **Modular.** V2 and V3 attach without rewriting V1.

---

## 4. User journeys

### 4.1 Researching a batch — the main path

1. Ali signs in and lands on the **Dashboard**.
2. Presses **Add videos**, pastes 12 links from a client brief.
3. Presses **Check videos**. Within seconds he sees all 12 with titles,
   thumbnails and lengths. Two are four-hour webinars and are refused for being
   over the limit; one is a TikTok link and is refused as unsupported.
4. He unticks two more that turn out to be irrelevant, leaving 7.
5. Presses **Transcribe 7 videos** and lands on **Job Details**, watching each
   move through downloading, extracting audio and transcribing.
6. He leaves it running and returns later. The dashboard shows the batch
   finished, one failed.
7. He opens the failed one, reads *"This video is unavailable — it may be
   private, deleted, or region-locked,"* and drops it.
8. He opens each transcript, exports the set as one Excel workbook, and starts
   writing.

### 4.2 Finding something remembered

Priya recalls a creator explaining a discount-code tactic months ago. She opens
**Search**, types `discount code`, and gets three transcripts with the sentence
shown. She opens the right one and copies the phrasing.

### 4.3 Onboarding a colleague

An admin opens **Settings → Team**, adds the new starter with a temporary
password. They sign in and change it. No IT ticket.

---

## 5. Functional requirements in detail

**Submission.** Accepts a pasted block; splits on newlines, commas and
whitespace. Per-URL verdicts — one bad link never rejects the batch. Duplicate
URLs within a batch are flagged. A video already in the library is flagged but
still selectable.

**Preview.** Runs before any download. Returns title, thumbnail, duration,
estimated size, creator, platform, plus a limits verdict with every failing
reason listed separately.

**Processing.** Stages: metadata → limits → download → audio → transcribe →
store. Progress is visible per video. Network failures retry with backoff; a
private or deleted video does not retry, because it never will succeed.

**Transcripts.** Stored with timed segments. Versioned per video. Full text
searchable.

**Search.** Phrase search across all transcripts, filterable by platform,
creator and date, returning the matching sentence as context.

**Export.** Seven formats. Bulk export returns one combined file for spreadsheet
and JSON, a ZIP otherwise. Filenames derive from video titles, sanitised.

**Accounts.** Admins create, deactivate and remove accounts. Deactivation takes
effect immediately, not when a session expires.

---

## 6. Non-functional requirements

| Area | Requirement |
|---|---|
| Performance | Preview of 20 URLs returns within ~15 seconds. Transcription speed is hardware-bound and reported honestly by the system check. |
| Reliability | A worker crash mid-job requeues that job rather than losing it. |
| Security | Passwords hashed with bcrypt. Tokens short-lived, with the account re-checked on every request. No user input reaches a shell. |
| Privacy | Video and audio deleted immediately after transcription. Transcripts are the only durable artefact. |
| Usability | Usable by a non-technical employee without training. |
| Maintainability | Adding a platform, a transcription provider or an export format is adding one file. |
| Portability | SQLite for development, PostgreSQL for production, switched by one setting. |

---

## 7. Future roadmap

**Version 2 — AI analysis.** For each transcript: main topic, hook, opening
pattern, storytelling framework, CTA, offer, emotional triggers, writing style,
structure, audience, tone, key learnings, quotes, viral elements, repeated
keywords, category. Runs as one additional pipeline stage and can backfill over
everything already collected.

**Version 3 — research system.** Compare creators and competitors, search
thousands of transcripts semantically, ask questions of past research, generate
hooks, CTAs, outlines, scripts and strategies, detect trends, and build a
searchable knowledge base.

Both are designed for behind interfaces: `LLMProvider` for model access, the
existing registry pattern for anything pluggable. V2 must be attemptable on free
local models first, with paid models a configuration change rather than an
architectural one.

---

## 8. Open questions

1. Expected volume — videos per week — so hardware can be sized properly?
2. Is a shared team login acceptable, or does each person need their own account
   from day one?
3. Retention: keep transcripts indefinitely, or expire them after a period?
4. Should clients ever see any of this, or is it strictly internal?
