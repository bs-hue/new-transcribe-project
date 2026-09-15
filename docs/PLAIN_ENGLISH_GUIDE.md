# Plain English Guide

**Who this is for:** you — the owner of this project, learning as we build.
**What it does:** explains the entire system with no assumed knowledge. Every technical word is defined the first time it appears.
**Relationship to the other docs:** the other seven specs are written for engineers. This one says the same things in ordinary language. If a spec confuses you, find the topic here first.
**Last updated:** 2026-07-28

---

## 1. What we are actually building

You paste a list of video links. The system fetches each video, listens to it, and gives you back the text of everything said — as a document, as subtitles, or as data. Optionally, it also writes you a summary.

That's it. Everything else in these documents exists to make that happen **reliably, for many people at once, on a small cheap server, without breaking.**

The hard part was never "turn speech into text." The hard part is:

- What if one of the 25 links is broken?
- What if the server runs out of disk space halfway through?
- What if someone closes their laptop mid-job?
- What if two people submit jobs at the same time and the server can only handle one?
- What if the whole thing crashes at 3am?

Most of the design you approved is answers to those questions.

---

## 2. The restaurant

This is the single most useful mental model. Hold onto it.

Imagine a restaurant.

| Restaurant | Our system | What it means |
|---|---|---|
| **Dining room** | **Frontend** | What the customer sees and touches. Menus, tables, the bill. |
| **Waiter** | **API** | Carries requests from the dining room to the kitchen, and food back out. The only way the two talk. |
| **Kitchen** | **Backend** | Where the actual work happens. Customers never go in here. |
| **Order rail** (the clip strip where tickets hang) | **Queue** | Orders wait their turn. One cook can only cook so fast. |
| **Pantry & record books** | **Database** | What we keep. Recipes made, who ordered what. |
| **Recipes** | **Business rules** | "A job with 3 failed items out of 5 is *partially completed.*" Rules that are true regardless of equipment. |
| **The oven** | **A tool we plugged in** | Replaceable. A recipe doesn't care if the oven is gas or electric. |

**The frontend and backend are completely separate.** This is deliberate and it's in your project rules. The dining room could be redecorated, or replaced with a food truck, and the kitchen wouldn't notice — because they only ever communicate by passing orders through the waiter.

---

## 3. The 60-second version of how it works

```
You paste links in the browser
        ↓
Browser sends them to the API                    ("here are 3 videos, please")
        ↓
API writes them down and immediately says "got it"   ← does NOT make you wait
        ↓
A worker picks up one link at a time:
        1. Ask the video site about it        (how long is it? is it private?)
        2. Download it
        3. Strip out just the audio
        4. Listen to the audio, write down every word
        5. (optional) Ask an AI for a summary
        6. Save the text — then DELETE the video file
        ↓
Meanwhile the browser asks every few seconds: "how's it going?"
        ↓
You see progress bars move. Then you download your transcripts.
```

The single most important line there is **"does NOT make you wait."**

If the API made you wait for a 40-minute video to transcribe, your browser would give up, and nobody else could use the site during those 40 minutes. So the API takes the order, hands it to a worker, and answers instantly. Everything else in the design follows from this one decision.

---

## 4. The cast of characters

Every tool we're using, what it actually is, and why it's there.

### The browser side ("frontend")

**React** — a toolkit for building screens out of reusable pieces. Instead of writing one giant page, you build small blocks (a button, a progress bar, a job row) and assemble them. Change the block once, it changes everywhere it's used.

**TypeScript** — JavaScript (the language browsers speak) with labels added. Plain JavaScript lets you accidentally treat a number as text and only find out when a user hits the bug. TypeScript catches it while you're writing. Think of it as spell-check for meaning.

**Vite** — the thing that runs your work-in-progress site on your own machine and rebuilds it instantly when you save a file. Also packages the finished site for the real server.

**Tailwind CSS** — how we make things look good. Instead of writing styling in a separate file far from the thing being styled, you attach small style labels directly: `padding-4`, `text-large`, `rounded`. Faster to work with, and much harder to end up with inconsistent spacing.

**shadcn/ui** — a set of pre-built, professionally designed, accessibility-correct components (dropdowns, dialogs, tables). Crucially, these get **copied into our project**, not installed as a package — so we own them and can change them, and no outside update can ever break our screens.

**TanStack Query** (also called React Query) — manages talking to the API. It remembers answers so we don't ask twice, and it handles "ask again every 3 seconds until this job is done, then stop." Doing that by hand is where bugs breed.

### The kitchen side ("backend")

**Python** — the programming language for the kitchen. Chosen because the entire world of speech-recognition and video tooling is written in Python.

**FastAPI** — the framework that turns our Python code into something a browser can talk to. It also checks every incoming request ("is that actually a valid URL?") before our code sees it, and automatically publishes a machine-readable description of the whole API, which keeps the frontend honest.

**Uvicorn** — the program that actually runs FastAPI and listens for internet traffic. FastAPI is the recipe; Uvicorn is the stove that's switched on.

### Storage

**Database** — organized permanent memory. Not a spreadsheet: a set of linked tables where the links are enforced. "This transcript belongs to this item, which belongs to this job, which belongs to this user" — and the database itself refuses to let those links break.

**SQLite** — a database that's just a single file on your laptop. Zero setup. Perfect while building.

**PostgreSQL** ("Postgres") — the grown-up database for the real server. Handles many people at once properly.

**SQLAlchemy** — lets us write one set of instructions that works on *both* SQLite and Postgres. Without it we'd write everything twice.

**Alembic** — version control for the database's *shape*. When we add a new column, Alembic records a numbered step: "step 7: add this column." Every copy of the database — your laptop, the server — runs the same numbered steps and ends up identical. Without this, the server's database and yours slowly drift apart, and nobody can remember why.

### The media tools

**yt-dlp** — the program that actually fetches a video from a URL. It's maintained by a community that constantly fixes it as video sites change their defences. This is the most fragile part of the entire system, and not because of anything we did.

**FFmpeg** — the Swiss army knife of audio and video. We use it for one job: throw away the picture, keep the sound, and convert it to the exact audio format the transcription model was trained on.

### The AI

**Whisper** — an AI model that listens to audio and writes down what was said. Made by OpenAI, and free to run on your own machine.

**faster-whisper** — the same Whisper intelligence, re-engineered to run roughly four times faster and use much less memory. This matters enormously to us, because our server has **no graphics card** and Whisper normally wants one. faster-whisper is what makes this project possible on a cheap server at all.

**"int8"** — a compression setting. The model normally does its arithmetic with very precise numbers; `int8` uses rougher ones. It's slightly less accurate, and much smaller and faster. On our hardware, that trade is worth it.

**LLM** (Large Language Model — e.g. Claude, GPT) — used *only* for the optional summary. Turned off by default, because each use costs money and sends your text to an outside company. Notice that transcription needs no outside AI service at all — it runs on our own server.

### Wrapping and shipping

**Docker** — a shipping container for software. Instead of "install Python, then FFmpeg, then these 40 libraries, hope the versions match," Docker builds a sealed box containing all of it. That same box runs identically on your Windows laptop and on a Linux server. It's the cure for "but it works on my machine."

**Docker Compose** — runs several containers together as one system: frontend box, backend box, database box, all wired up, started with one command.

**Nginx** — sits at the very front of the real server. Hands out the website files, forwards `/api` requests to the backend, and handles the padlock (HTTPS). It's very good at those jobs and frees the backend to do only real work.

**Git** — records every version of every file, forever, with a note about why it changed. It's how you can always go back, and how you'll see exactly what I changed and when.

---

## 5. Why the code is split into layers

This is the one idea worth genuinely understanding, because it explains the shape of every folder you'll see.

### The problem

Say we wrote the transcription rules and the Whisper code tangled together in one file. Later, we discover the server is too slow and we want to use a paid transcription service instead.

In tangled code, "swap the transcription tool" means opening up and re-testing everything, including rules that have nothing to do with transcription. That's how projects die.

### The fix: recipes don't name brands

We split the code into four layers, and enforce one rule: **inner layers know nothing about outer layers.**

```
   ┌──────────────────────────────────────────────┐
   │  Interface   — the waiter                     │  takes web requests,
   │                                               │  checks them, replies
   ├──────────────────────────────────────────────┤
   │  Application — the head chef                  │  "to do a job: download,
   │                                               │  extract, transcribe, save"
   ├──────────────────────────────────────────────┤
   │  Domain      — the recipe book & house rules   │  what a Job IS, when it's
   │                (knows nothing about the world) │  "failed", what's allowed
   ├──────────────────────────────────────────────┤
   │  Infrastructure — the actual equipment         │  yt-dlp, FFmpeg, Whisper,
   │                (plugs into the recipes)        │  the database, the internet
   └──────────────────────────────────────────────┘
```

The **domain** is the heart. It contains sentences like *"a job where some items succeeded and some failed is called partially completed"* and *"a private video must never be retried."* These are true no matter what tools we use. So the domain mentions no tool by name — not Whisper, not the database, not the internet.

### Ports and adapters — the socket idea

The recipe says: **"I need something that turns audio into text."** That requirement is a **port** — a socket shape.

Then, separately, we build a plug that fits: a **faster-whisper adapter**. Later we can build a different plug — a paid-API adapter — and the recipe never changes. Same socket, different plug.

This is why you kept seeing names like `TranscriptionProvider` and `QueueService` in the specs. Each one is a socket, deliberately placed where we expect to change equipment later.

**What this buys you concretely:** if Phase 0a shows the server is too slow, we swap one plug. Not a rewrite. That's not a theoretical benefit — given your hardware, it's a genuinely likely scenario, which is exactly why the socket is there.

**What it costs you:** more files, and more hops to follow when reading the code. That's a real cost. It's worth it here specifically because we already know several plugs will change.

---

## 6. The journey of one video, and everything we do to protect it

Here's what happens to a single link, with the reason for each step.

### Step 0 — Ask before fetching

We ask the video site for *information only*: how long is this? Is it private? Is it a live stream? Is it actually a playlist?

**Why:** it costs almost nothing and prevents expensive mistakes. A 6-hour video gets rejected in one second instead of after a 20-minute download. And if you accidentally paste a **playlist** link, we catch it — otherwise one paste could quietly become 200 downloads and take the whole server down.

### Step 0.5 — Check there's room

Is there enough free disk space?

**Why this is the safeguard I pushed hardest for:** your server has a small disk. If it fills completely, the **database stops working**, and the entire application dies — from one oversized video. So we check first, and if space is tight the job politely waits instead of filling the disk.

### Step 1 — Download

Fetch the video into a temporary folder, with a **stopwatch running**.

**Why the stopwatch:** our server transcribes **one video at a time**. If a download hangs forever on a dead connection, it holds the only slot — and *everyone's* jobs stop. Nobody gets an error, nobody gets a transcript, everything just silently freezes. The stopwatch turns a total system stall into a single failed item.

### Step 2 — Extract the audio

Throw away the video, keep the sound, convert it to the exact format Whisper expects.

**Why:** the picture is dead weight, and matching Whisper's expected audio format avoids quality surprises.

### Step 3 — Transcribe

Whisper listens and writes. This is the slow, expensive step — minutes, not seconds.

Two details:

- It runs in a **separate program from the API.** Whisper is a CPU glutton; if it ran inside the API, the website would go sluggish for everyone whenever anyone transcribed anything.
- **Silence detection is on.** It skips silent stretches — faster, and it avoids a known Whisper quirk where it "hears" words in silence and invents them.

### Step 4 — Summarize (optional, off by default)

Send the text to an AI service for a summary.

**Why off by default:** it costs money per use, and it sends your content to another company. That should be a deliberate choice, not a surprise. And if it fails, **the transcript is still saved** — we never lose expensive work because a bonus feature broke.

### Step 5 — Save the text, delete the video

The transcript goes in the database. The video and audio files are **deleted immediately.**

**Why:** small disk. Also, subtitle files (`.srt`, `.vtt`) are *not* saved — we regenerate them the instant you click download, because generating them takes microseconds and storing four versions of every transcript would waste the one resource we're short of.

**Important detail:** deletion happens **even when things go wrong** — failure, timeout, cancellation. Cleaning up only after *success* is a classic bug: failures are exactly when temp files pile up, and it's the failure case that eventually fills your disk.

---

## 7. The four "what if it breaks" protections

These were the significant gaps I found in your specs. Each one is a real scenario, not paranoia.

### "What if the server restarts mid-job?"

Right now, jobs run inside the API program. If it restarts — a crash, a deploy, a power blip — anything in progress simply vanishes. The item sits marked "in progress" forever, and no one ever notices.

**The fix — a name tag with a timestamp.** A worker starting a job stamps it: *"I'm working on this, as of 10:42."* It re-stamps every few seconds while working.

A separate checker looks for stale stamps. If an item says *"in progress as of 10:42"* and it's now 11:15, the worker is clearly gone — so the item goes back in the queue.

**Why it has to work this way:** without the timestamp you must choose between two bad options — restart *everything* that looks in-progress (so work already running gets done twice) or restart *nothing* (so crashed items are stranded forever). The stamp tells us which items are genuinely alive.

### "What if I paste the wrong link and want to stop?"

Cancelling used to be undefined — the button existed with nothing behind it.

Now: items not started yet stop immediately. A download in progress is killed instantly. A transcription in progress checks "should I stop?" **between sentences** — so it stops within seconds rather than finishing a 40-minute video you no longer want.

**Why this matters more than it sounds:** with one video at a time, a mistaken 3-hour paste doesn't just waste your time — it blocks every other user until it finishes.

### "What if a link fails for a silly reason?"

Video sites fail temporarily all the time — a network hiccup, a rate limit.

So we **sort failures into two piles:**

- **Worth retrying** — network error, timeout, "slow down." Try again up to 3 times, waiting longer each time.
- **Never retry** — the video is private, deleted, a playlist, or too long. Trying again is guaranteed to fail.

**Why sorting matters:** retrying a deleted video three times burns your scarce CPU and delays other people's work, for a certain failure. And you can retry one failed item by hand — you should never have to resubmit 24 working links to fix the one that broke.

### "What if I lose the transcripts?"

Transcripts are the entire value of this product. They cost real server time to create, and if the source video is later deleted from the internet, **they can never be recreated.** One disk failure on a single server would lose everything.

So: a nightly copy of the database, stored **off the server**, and — this is the part people skip — **we actually practice restoring it.** An untested backup isn't a backup; it's a hope.

---

## 8. How logging in works (in ordinary terms)

Think of a festival with a wristband policy.

- **Access token = the wristband.** It gets you in anywhere, and it **expires after 15 minutes.** It's kept only in your browser's memory — never written to disk. If it's stolen, the thief gets 15 minutes.
- **Refresh token = your ticket in the locker.** Long-lived. When your wristband expires, you show the ticket and get a fresh one.

The ticket is stored so that **the website's own code cannot read it** (an "HttpOnly cookie"). If someone ever manages to inject malicious code into our page, they can steal a 15-minute wristband — annoying. They cannot steal the ticket — which would be serious.

**Passwords** are never stored. We store a scrambled fingerprint (using Argon2) which cannot be reversed. When you log in, we scramble what you typed and compare fingerprints. Even if someone stole our entire database, they would not have anyone's password.

**One correction I made to the original plan:** it named a password library (`passlib`) that has been unmaintained for years. Using an abandoned library in the login system is exactly where you don't want one — so we use `argon2-cffi` directly instead.

---

## 9. Your job and my job

You don't need to write code. But this only works if you do these things — and they're genuinely the hard parts.

**Yours:**

1. **Decide what "good" means.** You're the only one who knows whether a 12-minute wait for a 40-minute video is fine or unacceptable. That answer changes the build.
2. **Test like a real user, and be picky.** After each phase you get something working. Try to break it. Paste a bad link. Close the tab mid-job. Every awkward moment you notice is worth more than a code review.
3. **Answer questions when I'm blocked.** Some choices are product choices, not technical ones, and I shouldn't guess at them.
4. **Ask "why" without hesitation.** If you can't explain a piece of this to a friend, I explained it badly. Say so.

**Mine:** write the code, explain what each file does before creating it (your rule, and a good one — it stops me sneaking in complexity), keep the docs true, and tell you plainly when something is a bad idea or when I'm uncertain.

**The one skill you can't avoid:** using a terminal — the text window where you type commands like `docker compose up`. Not programming; more like knowing a few phrases in a foreign country. Five or six commands cover almost everything you'll do.

---

## 10. What to install (Windows)

Not needed until we start Phase 0. Listed here so you can get it out of the way.

| Tool | Why | Note |
|---|---|---|
| **VS Code** | Where you'll read and edit files | Free, from Microsoft |
| **Git** | Records every version of the project | Includes a terminal ("Git Bash") |
| **Docker Desktop** | Runs the whole system with one command | Needs WSL2 — its installer sets this up. Works on Windows 11 Home |
| **Python 3.11+** | The backend language | Tick **"Add Python to PATH"** during install |
| **Node.js (LTS)** | Runs the frontend build tools | LTS = the boring, stable one. Correct choice |

With Docker, you may not need Python and Node installed directly — but having them makes day-to-day work quicker.

---

## 11. What each phase gives you

Every phase ends with something you can actually see and poke. That's deliberate: you should never wait months to find out whether this is working.

| Phase | What happens | What **you** can do at the end |
|---|---|---|
| **0a** | Three experiments on the real server | Know whether the plan works at all — before spending money on building |
| **0** | Skeleton set up | Start the system; see a page and a "server is healthy" reply |
| **1** | Accounts and login | Register, log in, log out. Confirm a normal user can't reach admin pages |
| **2** | The engine (no pretty screens yet) | Watch a real URL become a real transcript. Unglamorous, and the biggest milestone |
| **3** | The actual website | Do the whole thing in a browser like a customer: paste, watch, download |
| **4** | AI summaries | Turn summaries on, see key points appear |
| **5** | Going live | Use it at a real web address. Practice a backup restore |

**Phase 2 is the moment of truth.** It'll look plain — you'll be reading raw data, not a pretty page. But when a URL turns into text, the product exists. Phase 3 just makes it pleasant.

---

## 12. Phase 0a — why we test before we build

Three questions, answered with throwaway experiments on the real server, before writing a single line of real code.

**1. Can the server actually run this?** Cheap hosting plans come in two kinds. One gives you a real computer you control. The other gives you a slice of a shared machine where you *cannot* install tools like FFmpeg. If yours is the second kind, this design can't run there at all — and we need to know that now, not in three months.

**2. Can the server actually download videos?** This is the one I most want tested, because it's counter-intuitive. YouTube blocks and challenges traffic from data centres, because that's where bulk scrapers live. Your home internet looks like a person; a server looks like a robot. **The result: this can work perfectly on your laptop and fail on your server** — and when it does, it looks exactly like a bug we wrote. One afternoon of testing now avoids weeks of confusion later.

**3. How slow is it, really?** We time transcription on the actual server. The answer sets the default quality setting and tells you what to honestly promise users. Right now, nobody knows this number — including me. Guessing it would be pretending.

**If the answer to #1 or #2 is no**, we change the plan: use a paid transcription service instead of doing it ourselves (one socket, one new plug — this is precisely the flexibility we built in), or move to a different server.

---

## 13. Glossary

Words I'll use. Come back here freely.

| Word | Means |
|---|---|
| **API** | The waiter. The backend's menu of things it will do, and how to ask. |
| **Endpoint** | One item on that menu, e.g. "create a job." |
| **Frontend / Backend** | Dining room / kitchen. |
| **Framework** | A pre-built structure you fill in, so you don't start from nothing. |
| **Library / Package / Dependency** | Someone else's code we use instead of writing our own. |
| **Repository ("repo")** | The project folder, with its full history. |
| **Commit** | One saved change with a note explaining why. |
| **Branch** | A safe side copy for work in progress, merged in when it's ready. |
| **Migration** | A numbered step that changes the database's shape. |
| **Schema** | The database's shape — what tables and columns exist. |
| **Query** | A question asked of the database. |
| **Async** | Doing something without making the caller wait. |
| **Queue** | A waiting line of work. |
| **Worker** | The thing that takes work off the line and does it. |
| **Concurrency** | How many things happen at once. Ours is **1** for transcription. |
| **Timeout** | A stopwatch that gives up. |
| **Cache** | Remembering an answer so you don't redo the work. |
| **Environment variable** | A setting kept outside the code — passwords, addresses. Never in Git. |
| **Token** | The festival wristband. Proof of who you are. |
| **Hash** | A one-way scramble. Used for passwords. |
| **RBAC** | Role-Based Access Control — permissions by role (admin vs normal user). |
| **CSRF** | An attack where another site makes your browser act as you. We block it. |
| **XSS** | An attack where bad code gets injected into a page. Why tokens live in memory. |
| **Container** | Docker's sealed box with everything pre-installed. |
| **Port (Clean Architecture)** | A socket shape — "I need something that does X." |
| **Adapter** | A plug that fits the socket — the actual tool. |
| **Domain** | The recipe book. Rules that don't depend on tools. |
| **Use case** | One complete action the system performs, e.g. "create a batch job." |
| **Entity** | A thing the system knows about: User, Job, Transcript. |
| **Idempotent** | Doing it twice has the same effect as once. Stops double-charging on a double-click. |
| **Test** | Code that checks other code, automatically, forever. |
| **CI** | A robot that runs all tests on every change, so nothing broken gets in. |
| **Linter / Formatter** | Tools that catch sloppiness and standardise layout, so no one argues about spacing. |
| **Logs** | The system's diary. First place to look when something breaks. |
| **Deploy** | Putting a new version on the real server. |
| **Rollback** | Putting the previous version back, fast. |
| **VPS** | Virtual Private Server — a rented computer you control. |
| **Stage** | Where an item is in the pipeline: downloading, transcribing, etc. |
| **Terminal state** | Finished for good: completed, failed, or cancelled. |

---

## 14. How to actually learn this while we build

Not "go take a Python course." Do these instead:

1. **Read every file I create, the same day.** You won't follow all of it. Notice the *shape*: names, how big it is, how it's organized. Familiarity comes before understanding, and it comes free.
2. **Ask "what would break if this line were wrong?"** The fastest route to understanding why something exists.
3. **Follow one thing end to end.** Pick the "New job" button. Trace it: button → API call → endpoint → use case → database → queue → worker. Once you've followed one path through all four layers, the architecture stops being abstract. Ask me to walk you through it.
4. **Break things on purpose, in dev.** Paste a nonsense URL. Turn off your wifi mid-job. Stop the database. Watching *how* it fails teaches more than watching it work — and it's genuinely how experienced engineers build intuition.
5. **Read the logs when it breaks.** Even at 20% comprehension. You'll start recognising patterns quickly.
6. **Keep a "why" list.** When you hit a decision you don't understand, check `TECHNOLOGY_DECISIONS.md` — it exists to answer exactly that. If the answer isn't there, ask, and I'll add it.

You will not be writing this system by the end. You **will** be able to read it, test it, judge it, and hold me to account on it — which is the job that actually determines whether this succeeds.

---

> **If any part of this document didn't land, that's a defect in the document, not in you.** Tell me which section and I'll rewrite it.
