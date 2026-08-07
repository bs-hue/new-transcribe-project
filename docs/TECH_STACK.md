# Technology decisions

Every dependency in Version 1, justified: what it does, what it costs, how it is
licensed, what else was considered, and why this one won.

**Version 1 total software cost: £0.** No paid API, no licence fee, no SaaS
subscription. The only money involved is the machine it runs on.

**Licence summary:** every dependency is MIT, BSD, Apache-2.0 or PSF — all
permissive. None are copyleft (GPL/AGPL), so nothing here obliges us to publish
our own source, and all are safe for internal commercial use.
The one exception to watch is discussed under [yt-dlp](#yt-dlp) — it is a
*terms-of-service* consideration, not a licensing one.

---

## Backend language — Python 3.11

**What it does:** runs the server, the pipeline and the workers.

**Cost:** free. **Licence:** PSF (permissive).

**Alternatives considered**

| | Verdict |
|---|---|
| **Node.js / TypeScript** | One language across the stack is genuinely attractive. But yt-dlp, ffmpeg bindings and every Whisper implementation are Python-first; using Node means shelling out to Python anyway, or accepting weaker wrappers. |
| **Go** | Faster and single-binary deploys. Same problem, worse: the speech-to-text and video-download ecosystems barely exist there. |

**Why Python:** the three hardest parts of this product — downloading from
platforms, processing audio, and speech-to-text — all have their best,
best-maintained implementations in Python. Choosing anything else means fighting
the ecosystem for the entire life of the project.

**Trade-off:** Python is slower than Go for raw request handling. Irrelevant
here — this workload is bounded by network and CPU-bound transcription, not by
how fast the web framework parses a request.

---

## Web framework — FastAPI

**What it does:** turns Python functions into HTTP endpoints, validates
incoming data, and generates live API documentation.

**Cost:** free. **Licence:** MIT.

**Alternatives considered**

| | Verdict |
|---|---|
| **Django + DRF** | Batteries included — admin panel, ORM, auth all built in. Far more framework than a 25-endpoint internal API needs, and its async support is bolted on rather than native. |
| **Flask** | Simplest of the three. But no built-in validation, no automatic API docs, and async support is an afterthought. We would end up rebuilding what FastAPI gives us. |

**Why FastAPI:** async-native (which matters when jobs sit waiting on downloads),
request validation comes free from the type hints we would write anyway, and
`/docs` is generated from the code — so the API documentation cannot drift out of
date. Fastest path from "typed function" to "correct endpoint".

**Trade-off:** smaller ecosystem than Django, and no admin UI. We do not need
one; account management is a five-field page we wrote in an afternoon.

---

## Database — SQLite (development) → PostgreSQL (production)

**What they do:** store videos, jobs, transcripts, segments and users.

**Cost:** both free. **Licences:** SQLite is public domain; PostgreSQL is the
PostgreSQL Licence (BSD-style).

**Alternatives considered**

| | Verdict |
|---|---|
| **MySQL / MariaDB** | Perfectly capable. PostgreSQL has stronger JSON support (we store the raw platform payload as JSON) and better full-text search, both of which this project uses directly. |
| **MongoDB** | Our data is strongly relational — a video has jobs, has transcripts, has segments. Modelling that in a document store means either duplicating data or doing joins in application code. Also, the licence (SSPL) is not OSI-approved. |

**Why this pair:** SQLite means `git clone && run` with zero setup, which makes
development and evaluation frictionless. PostgreSQL is the obvious production
choice and requires **no application code change** — only `DATABASE_URL`. The
schema deliberately avoids SQLite-specific column types so the move is clean.

**Trade-off:** SQLite handles one writer at a time. Fine for a couple of workers
(WAL mode lets reads continue during writes), not fine for a busy multi-user
deployment — hence the switch for production.

---

## Video downloading — yt-dlp

**What it does:** reads video metadata and downloads from YouTube, Instagram and
~1,800 other sites.

**Cost:** free. **Licence:** Unlicense (public domain).

**Alternatives considered**

| | Verdict |
|---|---|
| **youtube-dl** | The original. Effectively unmaintained — updates lag platform changes by months, meaning long stretches where downloads simply fail. yt-dlp is its actively maintained fork. |
| **Paid APIs (Apify, RapidAPI scrapers)** | Roughly $0.005–0.05 per video, so ~$50–500/month at 100 videos/day, plus a hard dependency on someone else's uptime. They mainly solve the anti-bot problem — which for our volume, cookies solve for free. |

**Why yt-dlp:** the de-facto standard, updated within days when a platform
changes, and the only realistic free option. Every alternative is a paid
wrapper around it or around the same techniques.

**⚠️ The one caveat worth reading.** This is a terms-of-service question, not a
licensing one. Automated downloading sits against YouTube's and Instagram's
published terms. Realistically this is fine for what we are doing — a human-scale
volume of publicly posted marketing content, used internally for research, with
the video deleted after transcription and never republished. It would **not** be
fine to bulk-harvest at scale, to redistribute the videos, or to pass the
content off as our own. Worth a conscious decision by someone senior rather than
a silent assumption, and worth revisiting if usage grows by an order of
magnitude.

---

## Audio processing — FFmpeg

**What it does:** extracts the audio track from a downloaded video, converts it
to the 16 kHz mono format speech models expect, and splits long audio into
chunks.

**Cost:** free. **Licence:** LGPL-2.1 (some builds GPL). We invoke it as a
separate program rather than linking to it, which keeps us clear of any copyleft
obligation.

**Alternatives considered**

| | Verdict |
|---|---|
| **GStreamer** | Comparable capability, much steeper learning curve, and far fewer people can debug it when it breaks. |
| **Python audio libraries (pydub, librosa)** | pydub shells out to FFmpeg anyway — it is a wrapper, not a replacement. librosa is an analysis library, not a converter, and is slow on large files. |

**Why FFmpeg:** it is the tool every other tool wraps. Universally installed,
universally documented, and handles every container and codec a platform might
serve us.

**Trade-off:** it must be installed on the machine (it is in the Docker image).
We call it with argument *lists*, never a shell string, so no user-supplied text
can ever reach a shell.

---

## Speech-to-text — faster-whisper (local)

**What it does:** turns audio into text with word-level timing. This is the
single most important choice in the project.

**Cost:** **free.** No API key, no per-minute charge, nothing leaves your
network. **Licence:** MIT (the underlying Whisper model is also MIT).

**Alternatives considered**

| | Cost | Verdict |
|---|---|---|
| **openai-whisper** (the original Python package) | Free | Same model, same accuracy — but 4× slower and uses substantially more memory for identical output. The closest genuine competitor, and faster-whisper simply beats it. |
| **Vosk** | Free | Lighter and faster on weak hardware. Noticeably less accurate, especially on accented speech and marketing jargon — which is most of what we transcribe. |
| **Hosted APIs** (OpenAI Whisper, AssemblyAI, Deepgram) | ~$0.006–0.015/min → roughly £30–60/month at 100 videos/day | Rejected on principle and on merit: a paid API doing something a free one does equally well, that also sends client research to a third party and grows in cost forever. |

**Why faster-whisper:** it is the *same Whisper model* the paid API uses,
re-implemented on CTranslate2 to run about four times faster with less memory.
Accuracy is equivalent to the paid API at the same model size. It costs nothing,
runs offline, and keeps client research in-house — which for an agency handling
competitor and client material is a real benefit, not just a saving.

**This is the only transcription option in the codebase.** The paid provider was
removed rather than left switched off, so no configuration mistake can send audio
to a third party or incur a charge. It remains in Git history if the decision is
ever revisited.

**Trade-offs, stated plainly:**

- **Speed depends on your hardware.** On a modest CPU server, roughly real-time
  or slower with the `base` model — a 10-minute video takes about 10 minutes.
  An NVIDIA GPU makes it 10–20× faster. The paid API is faster on a small
  machine.
- **Accuracy depends on model size.** `base` is good; `small` is noticeably
  better and about 2× slower; `large-v3` matches the best paid services but
  wants a GPU. Change `FASTER_WHISPER_MODEL` — no code change.
- **First run downloads the model** (~150 MB for `base`), cached thereafter.

**If it is too slow:** the levers are `FASTER_WHISPER_COMPUTE_TYPE=int8`, a
smaller model, lower `WORKER_CONCURRENCY`, or a machine with an NVIDIA GPU — in
that order. All free. See
[`docs/SETUP.md`](SETUP.md#if-transcription-is-too-slow).

---

## Authentication — JWT (PyJWT + bcrypt)

**What they do:** PyJWT issues and verifies signed sign-in tokens; bcrypt hashes
passwords so a stolen database cannot be read.

**Cost:** free. **Licences:** PyJWT is MIT; bcrypt is Apache-2.0.

**Alternatives considered**

| | Verdict |
|---|---|
| **Server-side sessions** | Simpler to reason about and revocable instantly. But they need shared session storage the moment there is more than one server, and they complicate a separate-frontend setup. |
| **Auth0 / Clerk / Firebase Auth** | Free tiers exist (Auth0 ~7,500 users, Clerk ~10,000). Genuinely good products. But this is an internal tool for maybe 20 colleagues — adding an external identity provider means an outage we do not control and a bill if the free tier changes. |
| **passlib** for hashing | The long-standing default, but its maintenance has slowed and it warns on recent bcrypt versions. Using `bcrypt` directly is fewer moving parts. |

**Why JWT:** no shared session store, works cleanly across a separate frontend
and API, and is the standard FastAPI pattern so every example and answer applies.

**Trade-off, stated honestly:** a JWT stays valid until it expires — you cannot
"log someone out" server-side. Mitigated two ways: tokens last 12 hours (one
working day), and **every request re-checks the account**, so deactivating
someone takes effect immediately even though their token is still technically
valid. There is a test that proves this.

---

## Frontend — React + TypeScript + Vite

**What they do:** React builds the interface, TypeScript catches mistakes before
they ship, Vite compiles and serves it.

**Cost:** free. **Licence:** all MIT.

**Alternatives considered**

| | Verdict |
|---|---|
| **Next.js** | More capable — server rendering, routing, image optimisation. All of that serves public, SEO-sensitive sites. This is a private internal tool behind a login: server rendering buys nothing, and it means running a Node server in production instead of serving static files. |
| **Vue / Svelte** | Both excellent, arguably nicer to write. React has a far larger hiring pool and component ecosystem, which matters more than syntax for a tool the agency will maintain for years. |

**Why Vite over Next.js:** the build output is plain static files, so production
is nginx serving a directory — a few MB of container, nothing to crash, nothing
to patch. Vite's dev server also starts in well under a second.

**Trade-off:** no server-side rendering, so the first paint waits for JavaScript.
Invisible on an internal tool on an office network.

---

## UI components — Tailwind CSS + shadcn/ui

**What they do:** Tailwind styles via utility classes; shadcn/ui provides
accessible components (dropdowns, tabs, selects) built on Radix UI.

**Cost:** free. **Licence:** both MIT.

**Alternatives considered**

| | Verdict |
|---|---|
| **Material UI / Ant Design** | Comprehensive and quick to start. But they are heavy, opinionated, and restyling them to look like anything other than Google or Alibaba is a fight. |
| **Bootstrap** | Familiar and fast. Dated look, and jQuery-era patterns that sit awkwardly with React. |

**Why shadcn/ui:** it is not a dependency in the usual sense — the component
source is **copied into our repo** (`src/components/ui/`). We own it, can edit
any component freely, and can never be broken by an upstream release or
abandoned by a maintainer. Accessibility (keyboard navigation, screen readers,
focus management) comes from Radix underneath, which is genuinely hard to get
right by hand.

**Trade-off:** copied code means no automatic updates — a fix upstream must be
pulled in manually. Deliberate: for an internal tool, stability beats currency.

---

## Deployment — Docker + Docker Compose on a Linux VPS

**What they do:** package the app so it runs identically everywhere, and start
both services with one command.

**Cost:** Docker Engine and Compose are free (Apache-2.0). Docker *Desktop*
requires a paid licence for companies over 250 staff or $10M revenue — not
applicable at your size, and irrelevant on a Linux server, which uses the free
Engine.

**Server cost:** roughly £20–40/month for a VPS with enough CPU for local
transcription (Hetzner, DigitalOcean, Contabo). This is the project's only
recurring cost.

**Alternatives considered**

| | Verdict |
|---|---|
| **Managed platforms (Railway, Render, Fly.io)** | Much easier to deploy. But they charge per resource, and this workload is CPU-hungry and long-running — exactly the shape that gets expensive fast. Local transcription would likely cost more than a VPS. |
| **Bare metal / systemd** | Cheapest and simplest at one machine. But "works on my machine" problems return, and there is no clean rollback. |

**Why Docker:** one command to start, identical behaviour in development and
production, and no need to install Python, Node, ffmpeg and the rest on the
server by hand.

**Trade-off:** an extra layer to understand, and images are large (the Whisper
dependencies are not small). Worth it for reproducibility.

---

## Where paid services would genuinely earn their place

Not in Version 1. But when the time comes, these are the cases where free
alternatives do *not* achieve the same result:

| Feature | Why free is not enough | Realistic option |
|---|---|---|
| Nuanced analysis of hooks, CTAs, storytelling (V2) | Needs genuine language understanding. Free local models (Llama, Mistral via Ollama) can attempt it but are markedly weaker at nuanced marketing judgement — and need a serious GPU to run at all. | Claude, GPT, or Gemini — pennies per transcript |
| Semantic search ("find videos *about* urgency") | Free embedding models exist and are decent. Premium ones are better, but this is the *closest* call on the list — try free first. | Local embeddings first; paid only if quality disappoints |
| Script generation, competitor intelligence, Q&A over the knowledge base (V3) | Long-context reasoning across many transcripts at once. Local models struggle badly here. | Claude or GPT |

**How this stays cheap:** the same registry pattern used for transcription
providers applies to LLMs. A future `LLMProvider` interface with implementations
for Ollama (free, local), Claude, OpenAI, Gemini, DeepSeek and Groq means the
choice is an environment variable, not an architectural commitment. **You can
start on free local models and switch only if quality demands it** — and the
switch costs one line of configuration, not a rewrite.

---

## Running cost summary

| Item | Version 1 |
|---|---|
| All software and libraries | **£0** |
| Transcription | **£0** (local) |
| Authentication | **£0** (self-hosted) |
| Database | **£0** (SQLite / PostgreSQL) |
| Server (VPS) | ~£20–40/month |
| **Total** | **~£20–40/month** |

For comparison, the same system built on paid transcription and hosted auth
would run roughly £80–150/month at 100 videos/day — and would grow with usage
rather than staying flat.
