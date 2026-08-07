# Setting up the Content Research Hub

A plain-language guide for getting this running the first time.

**Who this is for:** whoever installs it. You do not need to understand the code,
but you do need to be comfortable opening a terminal and copying commands. If
that sentence made you uneasy, hand this page to whoever manages your laptops or
servers — it will take them under an hour.

**How long it takes:** about 30 minutes, most of it waiting for downloads.

---

## Before you start, you need two things

**1. A computer to run it on.**
For a first trial, someone's laptop is fine. For the whole team, you want an
always-on machine — a small cloud server (roughly £20–40/month) or a spare office
machine that stays switched on. It needs about 10 GB of free disk space.

Because transcription runs **on your own machine**, the machine matters more than
it would otherwise. More CPU cores means faster transcription. An NVIDIA graphics
card makes it dramatically faster, though it is not required.

**2. Docker installed** (recommended), or Python 3.11 and Node 20.
Docker is a tool that runs the app in a self-contained box so you don't have to
install its ingredients one by one. Free, from [docker.com](https://docker.com).

**That's it — there is no third thing.** No API key, no account to sign up for,
no card to enter. The whole system runs on free software, and transcription
happens locally, so no video or transcript ever leaves your network.

---

## Path A — with Docker (recommended)

### Step 1: Get the code onto the machine

```bash
git clone https://github.com/bs-hue/bulk-transcript-agent.git
cd bulk-transcript-agent
git checkout claude/social-media-research-hub-len3dw
```

That last line matters — the work lives on that branch, not on `main` yet.

### Step 2: Create your settings file

```bash
cp .env.example .env
```

This makes a copy of the example settings that you're then going to edit. The
original stays as a reference.

### Step 3: Set up your first account

Open `.env` in any text editor. Fill in these three lines:

```
BOOTSTRAP_ADMIN_EMAIL=you@youragency.com
BOOTSTRAP_ADMIN_PASSWORD=pick-something-long
JWT_SECRET=paste-a-long-random-string-here
```

- The first two create your admin account automatically on first start. Once
  you've signed in and changed the password, you can blank them out.
- `JWT_SECRET` is what proves a sign-in is genuine. **Any long random string
  works** — mash the keyboard for 50 characters, or if you have Python handy:
  `python3 -c "import secrets; print(secrets.token_urlsafe(48))"`.
  The app refuses to start in production if you leave the default.

You do **not** need to touch the transcription settings — local transcription is
already the default.

Save and close.

> ⚠️ **This file holds passwords.** Don't email it, don't paste it into Slack,
> don't commit it to GitHub. The project already keeps `.env` out of version
> control.

### Step 4: Start it

```bash
docker compose up --build
```

The first run takes 5–10 minutes because it's downloading everything it needs.
Later starts take seconds. Leave this window open — closing it stops the app.

### Step 5: Run the system check

Before opening the app, ask it whether this machine can actually do the job.
In a **second** terminal window:

```bash
docker compose exec api python -m app.cli doctor --deep
```

You'll get a plain-English report:

```
  [OK  ] Python version            Python 3.11.9
  [OK  ] ffmpeg (audio)            /usr/bin/ffmpeg
  [OK  ] Database                  SQLite reachable
  [OK  ] Sign-in secret            set and long enough
  [OK  ] No paid services          transcription providers: faster_whisper, stub — all free and local
  [OK  ] Speech-to-text            faster_whisper · model 'small' · runs locally, free
  [OK  ] Transcription self-test   heard "The hook is the first three seconds of
                                   the video." in 2.1s (1.7x realtime)

Everything checks out. You are ready to add videos.
```

`--deep` downloads the speech model (~150 MB, once) and transcribes a bundled
3-second clip. **This is the single most useful command in the project** — it
proves the whole chain works, and the "1.7x realtime" figure tells you roughly
how fast transcription will be on this machine before you commit to anything.

Anything that says `FAIL` comes with a specific instruction for fixing it.

### Step 6: Open it and sign in

Go to **http://localhost:3000** in a browser and sign in with the email and
password you put in `.env`.

You land on the **Dashboard**. It will be empty — no research yet — with a button
to add your first videos. That's it, you're running.

If you skipped Step 5, you can run the same check from inside the app instead:
**Settings → System check → Full check, with transcription**. Same result, no
terminal.

To stop it: press `Ctrl+C` in the first terminal window.

> **One honest note:** I verified the manual path (Path B) end to end on a real
> machine — installed it, ran it, clicked through every screen. I could **not**
> run a Docker build in my environment, so treat your first `docker compose up`
> as the real test. If it errors, the manual path below definitely works, and the
> error message will tell whoever's helping you exactly what's missing.

---

## Path B — without Docker

You'll need **Python 3.11+**, **Node 20+**, and **ffmpeg** installed. On a Mac
with Homebrew: `brew install python@3.11 node ffmpeg`.

Open two terminal windows.

**Window 1 — the engine:**

```bash
cd bulk-transcript-agent/backend
python3 -m venv .venv
source .venv/bin/activate
pip install -e .
cp ../.env.example ../.env      # then edit ../.env as in Step 3 above
python -m app.cli doctor --deep            # check this machine can run it
python -m app.cli create-user --email you@youragency.com --admin
uvicorn app.main:app --port 8000
```

The `create-user` line will prompt you for a password twice. (You can also let
`BOOTSTRAP_ADMIN_*` in `.env` do this for you.)

**Window 2 — the website:**

```bash
cd bulk-transcript-agent/frontend
npm install
npm run dev
```

Then open **http://localhost:5173** (Vite's dev server port — Docker uses 3000).

Both windows need to stay open while you use the app.

---

## About transcription speed

Transcription runs on your own machine, so speed depends on your hardware. This
is the main thing to understand about the setup.

**Roughly what to expect** with the default `small` model on a normal CPU:
somewhere around half to twice the length of the video itself. A 30-second Reel
takes well under a minute; a 10-minute video takes roughly 10–20 minutes. With
an NVIDIA graphics card, 10–30× faster. Every job logs its actual speed, so you
never have to guess — see "Making bulk transcription faster" below.

**The accuracy dial** is `FASTER_WHISPER_MODEL` in `.env`:

| Setting | Speed | Accuracy | Good for |
|---|---|---|---|
| `tiny` | Fastest | Rough | Nothing serious |
| `base` | Fast | Fine in clear English, poor in Hindi | Quick English gist |
| `small` | ~2× slower than base | Workable | Quick English batches |
| `medium` | ~2× slower again | Good | Decent Hindi |
| `large-v3-turbo` *(default)* | About Medium's speed | Near-best | **Hindi and Hinglish without a GPU** |
| `large-v3` | ~5× slower than Turbo | Best | Only worth it with a GPU |

**Turbo is the important one if you have no GPU.** It is Large with a much
smaller decoder — 4 layers instead of 32 — which is where nearly all the time
goes. On Hindi it still produces Devanagari and keeps English product names in
English, which is the behaviour that makes a transcript usable, at roughly a
fifth of Large's cost.

Change the value, restart, done. Existing transcripts are untouched — a new
transcription is added as a new version.

You can also change this from **Settings → System → Accuracy** without touching
any file or restarting anything.

**Two other useful settings:**
- `WORKER_CONCURRENCY` — how many videos transcribe at once. On a small server
  leave it at `1` or `2`; more will just make everything slower.
- `FASTER_WHISPER_COMPUTE_TYPE=int8` — noticeably faster on CPU for a small
  accuracy cost. Worth trying if speed is the problem.

### If transcription is too slow

In order of what to try:

1. **`FASTER_WHISPER_COMPUTE_TYPE=int8`** — often a large speed-up on CPU for a
   small accuracy cost. Try this first; it's free and takes seconds.
2. **`FASTER_WHISPER_MODEL=tiny`** — faster again, noticeably rougher. Fine when
   you only need the gist.
3. **`WORKER_CONCURRENCY=1`** — counter-intuitive, but on a machine with few
   cores, running two transcriptions at once makes *both* slow. One at a time
   often finishes a batch sooner.
4. **A machine with an NVIDIA graphics card** — 10–20× faster. The single
   biggest improvement available, and it's a hardware decision, not a software
   one.

There is deliberately no paid API in this system. If you ever conclude the
hardware route isn't workable for your volume, that's a decision to raise
explicitly with costs attached — not something the app should quietly do.

---

## Your first test — do this before telling the team

1. Open http://localhost:3000 and sign in.
2. Paste one short YouTube link. Something under two minutes.
3. Click **Check videos**. You should see the title, thumbnail and length appear.
   *Nothing has downloaded yet* — this is the preview step.
4. Click **Transcribe 1 video**.
5. Watch the progress: Downloading → Extracting audio → Transcribing.
6. When it finishes, click **Open** and read the transcript.
7. Click **Export** and download it as a Word document.

If all seven steps work, the system is genuinely working. If step 5 fails, see
the troubleshooting table below.

**The first transcription is slower than the rest** — it downloads the speech
model (~150 MB) before it can start. That happens once.

### Then add your team

Go to **Team** in the top navigation (admins only) → **Add person**. Give each
person a temporary password and ask them to change it after signing in. Choose
*Member* for most people — *Admin* only for those who should manage accounts.

---

## Instagram needs one extra setup

Instagram refuses to serve videos to anonymous software — this isn't something
the app can work around. You need to give it a logged-in browser session.

**Use a throwaway Instagram account, not a personal or client one.** Automated
access can get an account rate-limited or locked.

Full instructions: [`docs/COOKIES.md`](COOKIES.md). It's a browser extension, an
export, and one line in `.env`.

YouTube works without any of this, unless a specific video is age-restricted.

---

## When something goes wrong

| What you see | What it means | What to do |
|---|---|---|
| "Cannot reach the server" | The website is running but the engine isn't | Check the engine's terminal window is still open and hasn't errored |
| "Unsupported URL" | Not a YouTube/Instagram video link | Check it's a link to *one video*, not a channel or profile |
| "That looks like a YouTube link, but not a single video" | Someone pasted a channel or playlist | Open the specific video and copy that link |
| "This video is unavailable" | Private, deleted, or blocked in your country | Nothing to fix — the video genuinely isn't accessible |
| "Requires an authenticated session" | Instagram, or an age-restricted video | Set up the cookies file (above) |
| "Sign in to use this endpoint" / bounced to login | Your session expired (they last 12 hours) | Sign in again |
| "Incorrect email or password" | Exactly that — the message is the same for a wrong password and an unknown email, on purpose | An admin can reset it: `python -m app.cli reset-password --email …` |
| "This account has been deactivated" | An admin switched the account off | An admin can reactivate it on the Team page |
| Server won't start: "JWT_SECRET must be set…" | `ENVIRONMENT` is not `development` and the signing key is still the default | Put a long random string in `JWT_SECRET` |
| "Transcription is not configured" | faster-whisper isn't installed properly | `pip install faster-whisper`, then restart |
| Transcription is very slow | Expected on modest hardware — it runs locally | Try `FASTER_WHISPER_MODEL=tiny` and `FASTER_WHISPER_COMPUTE_TYPE=int8`, or see the fallback above |
| "Video is 3:12:00, which exceeds the 2:00:00 limit" | Working as designed | Raise `MAX_VIDEO_DURATION_SECONDS` in `.env` if you genuinely need longer |
| A job says **failed** | Varies — the reason is shown on screen | Click **Try again**; network hiccups usually resolve on a retry |

**Before anything else, run the system check.** It catches most of the above and
tells you exactly what to do:

```bash
# Docker:
docker compose exec api python -m app.cli doctor --deep
# Without Docker (from the backend folder, with the venv active):
python -m app.cli doctor --deep
```

**The golden rule:** almost every problem shows a specific message on screen or in
the terminal window. Copy that message when asking for help — it's the difference
between a two-minute fix and an afternoon.

---

## Settings worth knowing about

All in `.env`. Restart the app after changing anything.

| Setting | Default | What it does |
|---|---|---|
| `MAX_VIDEO_DURATION_SECONDS` | `7200` (2 hours) | Rejects longer videos before downloading |
| `MAX_VIDEO_FILESIZE_BYTES` | 2 GB | Rejects bigger downloads |
| `MAX_URLS_PER_REQUEST` | `50` | How many links can be pasted at once |
| `WORKER_CONCURRENCY` | `2` | How many videos process simultaneously. Local transcription is CPU-hungry — on a small server, `1` or `2` |
| `FASTER_WHISPER_MODEL` | `base` | Accuracy vs speed — see the table above |
| `ACCESS_TOKEN_EXPIRE_MINUTES` | `720` | How long a sign-in lasts. 720 = 12 hours = one working day |
| `TRANSCRIPTION_LANGUAGE` | *(empty)* | Leave empty to auto-detect. Set to `en`, `hi` etc. if you know the language — slightly more accurate |

---

## Looking after it

**Where your research lives.** Everything the team collects is in one file:
`data/app.db` (or the `api-data` volume under Docker). **Back this up.** That file
is the entire library — losing it means losing every transcript.

Downloaded videos are *not* kept — they're deleted straight after transcription,
which keeps disk usage low and avoids stockpiling other people's content. The
transcripts are what's permanent.

**Updating.** When there's new work to pull in:

```bash
git pull
docker compose up --build
```

**Growing.** It runs on a simple database that's fine for thousands of
transcripts. If it ever outgrows that, switching to a bigger database is a
one-line settings change, not a rebuild — that was planned for.

---

## Who to ask

- **Technical setup questions** → whoever manages your IT
- **Why each piece of technology was chosen, and what it costs** →
  [`docs/TECH_STACK.md`](TECH_STACK.md)
- **What the system does and why it's built this way** →
  [`TECHNICAL_ARCHITECTURE.md`](TECHNICAL_ARCHITECTURE.md)
- **Connecting other software to it** → [`docs/API_SPECIFICATION.md`](API_SPECIFICATION.md), or the
  self-documenting page at http://localhost:8000/docs while it's running

---

## Getting good results in Hindi and other Indian languages

Whisper is multilingual, but its accuracy varies enormously by model size, and
the gap is far wider outside English. If the Hindi coming back looks like
nonsense, it is almost always one of these two settings — not the audio.

**1. Name the language.** Go to **Settings → System → Spoken language** and pick
**Hindi**. Automatic detection listens to a few seconds only; on a Reel that
opens with music or an English word, it regularly guesses Urdu, Nepali or
Marathi, and then transcribes the entire video through the wrong language.
Naming it removes that failure completely.

**2. Use a big enough model.** **Settings → System → Accuracy**:

| Model | Hindi quality | Speed on a typical laptop |
|---|---|---|
| `tiny`, `base` | Not usable — roughly half the words wrong | Fastest |
| `small` | Usable. The realistic minimum for Hindi | ~2× slower than base |
| `medium` | Clearly better; handles Hinglish and accents | ~2× slower than small |
| `large-v3` | Best available | Needs a strong machine or an NVIDIA GPU |

Start at `small`. If the output is close but not right, move to `medium`. Each
model downloads once, the first time you use it.

**Hinglish** — Hindi with English words mixed in — is normal in this content and
Whisper handles it, but it needs `medium` or better to do it well. Set the
language to Hindi even for Hinglish; the English words still come through.

**3. Tell it the words you use.** **Settings → System → Words to expect.**
Whisper works from sound alone, so any word it has never met comes out as
whatever it sounds nearest to — which is how "black obsidian" becomes
"abheech", and why product and brand names are usually the worst-transcribed
part of a marketing video. List them, comma separated:

```
black obsidian, tiger eye, rudraksha, Vastu, kundali, evil eye, bracelet
```

Change it per client whenever the vocabulary changes. It applies to the next
job, with no restart.

**A note on script.** With the language set to Hindi, transcripts come back in
**Devanagari** (देवनागरी), not romanised Hinglish. That is Whisper working
correctly — Devanagari is what it is trained to produce for Hindi, and it is
substantially more accurate than any romanisation. If a transcript comes back
in Latin letters that read like garbled Hindi, that is the signature of the
language *not* being set: the model has been forced to spell Hindi sounds using
another language's alphabet.

---

## Making bulk transcription faster

Transcription runs on your own machine, so speed is bounded by that machine.
These are the levers, in order of how much they matter.

**1. An NVIDIA GPU changes everything else.** With `FASTER_WHISPER_DEVICE=auto`
a GPU is found and used automatically, and transcription becomes roughly ten to
thirty times faster. If a batch of 20 videos is a regular job, one machine with
a GPU is worth more than every other tuning option combined.

**2. Match workers to cores.** `WORKER_CONCURRENCY` is how many videos process
at once. The app now divides the CPU between them automatically, so two workers
take half the machine each rather than fighting over all of it. As a rule:

| Machine | WORKER_CONCURRENCY |
|---|---|
| 4 cores | 1 |
| 8 cores | 2 |
| 16 cores | 3–4 |

More workers than that makes a batch slower, not faster.

**3. Use the smallest model that is good enough.** `medium` is roughly four
times slower than `small`. If your English content is clear, `small` is plenty
for it — and you can change the setting between batches.

**4. Watch what it actually does.** Every transcription logs its real speed:

```
Transcribed 512s of audio in 210s (2.4x real time, model=small, cpu)
```

Above 1× means faster than real time. That single number tells you what a batch
will cost before you start it: at 2.4×, twenty 3-minute Reels take about 25
minutes. If it reads below 1×, the model is too big for the machine.

---

## Checking which code is actually running

Two things look identical from the outside: a fix that did not work, and a fix
that was never loaded. This tells them apart.

```bash
docker compose exec api python -m app.cli doctor
```

The report names the model, the language and the vocabulary in force. If those
do not match what the Settings screen shows, the container is running an older
image — `git pull` then `docker compose up --build`, and note that `--build` is
not optional after a pull.

A faster version of the same question:

```bash
docker compose exec api python -c "import app.services.transcription.languages"
```

Silence means current code. `ModuleNotFoundError` means the image predates it.

**The transcript screen answers this too.** Under the text it prints the
provider and the language, like `faster-whisper · hi`. If a Hindi video reads
`· en`, the language was detected wrongly and everything above it is the model
spelling Hindi with an English alphabet — no amount of re-reading will improve
it. Set the language and transcribe it again.

---

## Using Sarvam AI instead of local transcription

Whisper is trained overwhelmingly on English. Getting good Hindi out of it needs
the largest model, and that model is slow on a machine without a graphics card.
**Saarika**, from Sarvam AI, is built for Indian languages: better on Hindi and
Hinglish, and it finishes in seconds because the work happens on their hardware.

**The trade-off, stated plainly:** the audio is uploaded to a third party. Your
original requirement was that no research leaves your network. For competitor
reels that are already public on Instagram this is likely fine. For anything a
client gave you in confidence, it is not. The local engine stays installed, and
switching back is one word.

### Turning it on

1. Create a free account at **sarvam.ai** and generate an API key.
2. In `.env`:

```
TRANSCRIPTION_PROVIDER=sarvam
SARVAM_API_KEY=your-key-here
```

3. Restart: `docker compose up`

### Checking which one you are on

```bash
docker compose exec api python -m app.cli doctor
```

The report now names it outright:

```
  [OK  ] Where audio is processed   faster_whisper — on this machine.
                                    Nothing is uploaded and nothing is charged.
```

or, with Sarvam configured:

```
  [WARN] Where audio is processed   sarvam — audio is uploaded to a third party
                                    for transcription.
```

That second line is a warning rather than an error, because it is a legitimate
choice — but nobody should discover it by reading a configuration file.

### What changes, and what does not

| | Local | Sarvam |
|---|---|---|
| Speed for 100 reels | 25–40 min | Minutes |
| Hindi and Hinglish | Good with `large-v3-turbo` | Purpose-built |
| Cost | Nothing, ever | Free allowance, then per-minute |
| Audio leaves your network | No | **Yes** |
| Server needed | 8 vCPU for comfort | The cheapest VPS will do |
| Works with no internet | Yes | No |

Everything else is identical — the same screens, the same search, the same seven
export formats. Only the engine changes.

### Languages

Saarika covers Hindi, English, Bengali, Gujarati, Kannada, Malayalam, Marathi,
Odia, Punjabi, Tamil and Telugu. **It has no Urdu**; if the spoken language is
set to Urdu it will detect instead of failing. The local engine handles Urdu, so
that is a reason to keep it for those videos.

### If it stops working mid-batch

Rate limits and expired free allowances surface as a failed job with a plain
message, and the queue retries it. If a whole batch fails, switch
`TRANSCRIPTION_PROVIDER` back to `faster_whisper` and re-run — the videos are
already downloaded and the research is not lost.
