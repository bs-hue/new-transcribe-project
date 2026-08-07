# UI/UX Specification

Deliverable for step 7 of the development workflow.

**Status: awaiting approval.** No screens are rebuilt until this document is
signed off — per the process gate between Documentation and Implementation.

---

## 1. Why this document exists

Version 1 was implemented before this specification was written. The result is a
UI that works but does not match the planned screen list. This document states
the intended design, records the gap, and defines what changes.

### What was specified vs what was built

| Planned screen | Built as | Verdict |
|---|---|---|
| **Login** | `/login` | ✅ Matches |
| **Dashboard** | — | ❌ **Missing entirely** |
| **New Job** | `/` "Add videos" | ⚠️ Exists, but not framed as a job |
| **Job Details** | — | ❌ **Missing entirely** |
| **Transcript Viewer** | `/library/:videoId` | ⚠️ Exists, but keyed on video, not job |
| **History** | `/library` "Library" | ⚠️ Exists under a different name |
| **Settings** | — | ❌ **Missing entirely** |
| *(not planned)* | `/search` | ➕ Extra |
| *(not planned)* | `/users` "Team" | ➕ Extra |

**Three screens are missing. Three are renamed or reshaped. Two are unplanned.**

### The root cause, stated plainly

The build is **video-centric**; the plan is **job-centric**.

In the plan, a *job* is the thing a user creates, watches, inspects and returns
to. In the build, a job is an internal queue record the user barely sees — the
library lists videos, and a failed job is nearly invisible unless you happen to
open the video it belongs to.

That is not a cosmetic difference. It changes what the user can see when
something goes wrong, and it is why Dashboard and Job Details have no natural
home in the current app.

---

## 2. Users and what each screen is for

| Role | Primary need |
|---|---|
| Content Writer / Copywriter | Read transcripts, export them, find past research |
| Creative Strategist | Compare creators, search across everything |
| Account Manager | Submit batches, see whether they finished |
| Administrator | All of the above, plus accounts and system settings |

Design rule throughout: **a non-technical person must never see a raw error, an
id, or a technical term without a plain-English explanation beside it.**

---

## 3. Screen specifications

### 3.1 Login

**Route:** `/login` · **Access:** public

| Element | Behaviour |
|---|---|
| Email, Password | Required. Errors appear above the form, never as a browser alert. |
| Sign in | Disabled while submitting; label becomes "Signing in…" |
| Failure message | Identical for wrong password and unknown email, so the page cannot be used to discover who has an account |
| Footer note | "No account? Ask an administrator on your team to create one." |

**Already built and conforming.** No change.

---

### 3.2 Dashboard — **built**

**Route:** `/` · **Access:** any signed-in user
**This becomes the landing page.** "New Job" moves to `/jobs/new`.

The question this screen answers: *what is happening right now, and what needs
me?*

**Layout, top to bottom**

1. **Greeting line** — "Good morning, Priya" and today's date.

2. **Four summary tiles**

   | Tile | Value | Links to |
   |---|---|---|
   | In progress | count of running + queued jobs | Job list, filtered to active |
   | Finished today | jobs completed since midnight (UTC) | Job list, filtered to completed |
   | Needs attention | failed jobs | Job list, filtered to failed |
   | Total research | videos with a transcript, all time | History |

   Each tile opens what it counted. *Total research* counts **videos**, not
   transcripts, because History lists videos — transcribing the same video
   twice must not make the tile and the screen it opens disagree.

   The *Needs attention* tile is the only one that changes colour — amber when
   above zero, neutral when zero. Nothing else competes for the eye.

3. **Active jobs strip** — every running or queued job with its live progress
   bar and current stage. Auto-refreshes every 2 seconds while any job is
   active, then stops. Empty state: "Nothing processing. Add videos to start."

4. **Recent research** — the six most recent transcripts as cards: thumbnail,
   title, creator, duration, when added. Clicking opens the Transcript Viewer.

5. **Primary action** — "Add videos" button, top right, always visible.

**Empty state (new account, nothing yet):** tiles hidden entirely; a single
centred panel — "No research yet. Paste your first YouTube or Instagram link."
with the Add videos button. First-run should not look like a broken dashboard.

---

### 3.3 New Job

**Route:** `/jobs/new` · **Access:** any signed-in user

Three steps, with the current step always visible as a numbered indicator.

**Step 1 — Paste URLs**
- Monospace textarea, one URL per line, comma and whitespace also accepted
- Live count: "12 URLs detected"
- Batch limit shown in the helper text, read from the server, never hardcoded
- Optional: language override (defaults to auto-detect)
- Action: **Check videos**

**Step 2 — Review** *(this is the step that saves the time — it must not be skippable)*

Each pasted URL becomes a row:

| State | Shown |
|---|---|
| Ready | Checkbox ticked, thumbnail, platform badge, title, creator, duration, estimated size |
| Already in library | As above plus a quiet "Already in library" note — still selectable |
| Over limits | Checkbox disabled, every failing reason in red, one per line |
| Warning | Selectable, reasons in amber (unknown duration, size close to limit) |
| Unsupported | Checkbox disabled, the URL as the title, reason in red |

Header states the counts and, explicitly, **"nothing has been downloaded yet"**.
Footer: **Back** and **Transcribe N videos**, the latter disabled at zero
selected.

**Step 3 — Submitted**
Redirect straight to **Job Details** for the new job. Progress is watched there,
not here — one place to look, not two.

---

### 3.4 Job Details — **built**

**Route:** `/jobs/:jobId` · **Access:** any signed-in user

The question this screen answers: *what happened to the batch I submitted?*

**Header** — job reference, who submitted it, when, overall status pill
(Queued / Running / Completed / Partly failed / Cancelled), and an overall
progress bar for the batch.

**Per-video list.** Each row shows the video and, critically, **which stage it
reached**:

```
Reading details → Checking limits → Downloading → Extracting audio
→ Transcribing → Saving → Done
```

Completed stages tick; the current one shows a progress bar; later ones stay
grey. A failed video shows the stage it failed at, the plain-English reason, and
a **Try again** button on that row alone.

**Row actions:** Open transcript (when done) · Try again (when failed) ·
Cancel (only while still queued — a running download is not interrupted).

**Auto-refresh** every 2 seconds while anything is active; stops when the batch
finishes so an idle tab is not polling forever.

---

### 3.5 Transcript Viewer

**Route:** `/transcripts/:transcriptId` *(currently `/library/:videoId`)*

**Header** — platform badge, title, creator, duration, word count, link to the
original video, and the actions: **Copy text**, **Export ▾**, **Delete**.

**Body — two tabs**
- **Full text** — continuous, generously spaced, comfortable to read
- **Timed segments** — timestamp in the left column, text on the right

**Export menu** lists formats read from the server, so adding one server-side
adds it here with no frontend change. Formats needing timestamps are disabled,
with a tooltip, when the transcript has no segments.

**When there is no transcript yet** (job still running or failed) this screen
shows the job's state and a link to Job Details rather than an empty page.

---

### 3.6 History

**Route:** `/history` *(currently `/library`)*

Rename only — the screen itself is right.

- Filters: platform, creator (debounced), date range, has-transcript
- Rows: checkbox, thumbnail, platform badge, title, creator, duration, date
- Multi-select → **Export selected** in any format; spreadsheet and JSON come
  back as one combined file, everything else as a ZIP
- Pagination showing "21–40 of 128"
- Empty state offers the Add videos action

**Open question for approval:** keep the name "Library", or rename to "History"
as specified? "Library" reads better for a research collection; "History"
matches the plan. **Recommendation: History in the navigation, since it is your
spec, and it pairs naturally with Jobs.**

---

### 3.7 Settings — **built**

**Route:** `/settings` · **Access:** see per-section notes

| Section | Who | Contents |
|---|---|---|
| My account | Everyone | Name, email (read-only), change password |
| Transcription | Admin | Model size with plain-English speed/accuracy guidance; language default. Changes apply to future jobs only. |
| System limits | Admin | Max duration, max file size, max URLs per batch, worker concurrency |
| Instagram access | Admin | Cookie file status: configured / not configured / expired, with a link to the setup guide |
| System check | Admin | Runs the same checks as `doctor` and shows the result in the browser — so nobody needs a terminal to diagnose a problem |
| Team | Admin | Existing `/users` screen, folded in here as a section |

Every admin setting states what it affects and whether it applies retroactively.
Nothing here silently changes past research.

Numbers are stored in the unit the backend needs — seconds, bytes — but never
shown alone. Each number field prints its value in plain English beside the box,
updating as it is typed: `7200` reads *2 hours*, `2147483648` reads *2.0 GB*.
The unit comes from the API's setting definition, so the screen hardcodes
nothing and a new setting arrives already legible.

---

### 3.8 Search — **built** *(kept, with approval)*

**Route:** `/search`

Not in the original screen list, but it is the feature that makes the collected
research compound, and it is the foundation of V3's semantic search. Retaining
it costs nothing and removing it would waste working code.

**Approved and kept.**

---

## 4. Navigation

```
Dashboard   New Job   Jobs   History   Search            [ user ▾ ]
                                                          ├ Settings
                                                          └ Sign out
```

- **Jobs** is a new list view at `/jobs`, filterable by status, linking to Job
  Details. It is how a user finds a batch from yesterday.
- **Team** moves out of the top bar into Settings, where account management
  belongs.
- Admin-only items are hidden, not disabled, for non-admins.

---

## 5. Cross-cutting rules

**Errors.** Always plain English, always paired with what to do. Never a raw
code or stack trace. The failing thing shows the error next to itself, not in a
banner at the top of the page.

**Loading.** Skeleton rows where the shape is known; a spinner with a label
otherwise. Never a blank screen.

**Empty states.** Every list has one, and every one names the action that fills
it.

**Destructive actions.** Delete asks for confirmation and says what else goes
with it ("this also deletes the transcript").

**Responsive.** Works from 360 px up. Tables scroll inside their own container;
the page body never scrolls sideways.

**Accessibility.** Visible keyboard focus everywhere, labels on every input,
colour never the sole carrier of meaning (status uses a word as well as a hue),
and `prefers-reduced-motion` respected.

**Theme.** Light and dark, both designed rather than inverted.

---

## 6. What changes, and the cost

| Change | Type | Effort |
|---|---|---|
| Build Dashboard | New screen | ~1 day |
| Build Job Details | New screen | ~1 day |
| Build Settings | New screen | ~1.5 days |
| Add Jobs list | New screen | ~0.5 day |
| Move New Job to `/jobs/new` | Route change | ~1 hour |
| Rename Library → History | Rename | ~1 hour |
| Move Team into Settings | Move | ~2 hours |
| Backend: dashboard summary endpoint | New endpoint | ~2 hours |
| Backend: settings read/write | New endpoints | ~0.5 day |

**Roughly 5 working days.** No existing backend work is discarded — the job
records, stages and progress the new screens need are already stored and already
exposed. What is missing is the screens that show them.

---

## 7. Approval

Please confirm, or correct, each of these before implementation begins:

1. **Dashboard as the landing page**, with New Job moving to `/jobs/new`
2. **The four dashboard tiles** — are those the right four numbers?
3. **"History" over "Library"** in the navigation
4. **Keeping the Search screen**
5. **Team folded into Settings** rather than a top-level item
6. **The Settings sections** — anything missing that your team will want to change?

Once approved, implementation proceeds screen by screen, each with tests and its
own commit, per the development workflow.
