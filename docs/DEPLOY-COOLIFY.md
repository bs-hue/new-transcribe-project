# Deploying to Coolify

Coolify builds the `docker-compose.yml` in this repository and puts a domain in
front of it. Everything below is the configuration it needs.

---

## 1. Point it at the right branch

**This is the most common mistake, and it produces an app that looks a week
old.** A deployment does not follow the repository — it stays on whatever commit
it last built.

In Coolify, on the application: **Configuration → Source**

| Field | Value |
|---|---|
| Repository | `https://github.com/bs-hue/bulk-transcript-agent` |
| Branch | `claude/social-media-research-hub-len3dw` |

Not `main`. `main` holds a placeholder commit and nothing else.

If the running site shows navigation reading *Add videos · Library · Search ·
Team*, it is an old build. The current app reads *Dashboard · New job · Jobs ·
History · Search*.

After changing the branch, press **Redeploy**. Turn on **auto-deploy** if you
want future pushes to go out on their own.

---

## 2. Which service the domain points at

Coolify must send the domain to **`web`**, on **port 80**.

`web` serves the site *and* forwards `/api` to the `api` container over the
private network between them. So one domain covers both, there is no second
address to configure, and no cross-origin request to permit.

**Do not give `api` a public domain.** It does not need one, and exposing it
publicly puts the job queue and the export endpoints on the open internet for no
benefit.

---

## 3. Environment variables

Set these in **Configuration → Environment Variables**. Coolify passes them to
the build, so `.env` is not used here — the file on your laptop stays where it
is and changes nothing about the deployment.

### Required

```
ENVIRONMENT=production
JWT_SECRET=<paste 48+ random characters>
PUBLIC_URL=https://your-domain-here
BOOTSTRAP_ADMIN_EMAIL=you@youragency.com
BOOTSTRAP_ADMIN_PASSWORD=<a real password>
```

`JWT_SECRET` — **the app refuses to start in production with the shipped
default.** That is deliberate: a known signing key means anyone can forge a
sign-in. Generate one:

```bash
python -c "import secrets; print(secrets.token_urlsafe(48))"
```

`PUBLIC_URL` — the full address including `https://`, no trailing slash.

`BOOTSTRAP_ADMIN_*` — creates the first account on first start. Sign in, change
the password, then clear both and redeploy.

### Transcription

```
TRANSCRIPTION_PROVIDER=faster_whisper
TRANSCRIPTION_LANGUAGE=hi
FASTER_WHISPER_MODEL=large-v3-turbo
WORKER_CONCURRENCY=1
```

For Sarvam instead — faster, better Hindi, and the audio leaves your server:

```
TRANSCRIPTION_PROVIDER=sarvam
SARVAM_API_KEY=<your key>
```

> If a job fails with **"Unknown TRANSCRIPTION_PROVIDER 'sarvam'"**, the
> deployment predates that provider. It is not a configuration problem — the
> build is old. See section 1.

`WORKER_CONCURRENCY=1` to begin with. Local transcription is the heaviest thing
this app does, and a small VPS running two at once finishes a batch later than
one running them in order. Raise it only if the server has cores to spare.

### Letting people create their own accounts

Sign-up is **off** unless you turn it on — an internal tool with an open
registration form is an internal tool anyone can join.

```
REGISTRATION_MODE=approval
```

| Value | Behaviour |
|---|---|
| `closed` *(default)* | No sign-up. An admin adds people in Settings → Team |
| `approval` | Anyone can request an account; an admin approves before they get in |
| `open` | Anyone who signs up is in immediately |

`approval` is the sensible choice for an agency. The sign-in page only shows a
"create an account" link when this is not `closed`, so if you cannot see one,
this is why.

### Optional

```
COOKIES_FILE=/data/cookies.txt     # Instagram; see docs/COOKIES.md
MAX_VIDEO_DURATION_SECONDS=7200
MAX_URLS_PER_REQUEST=50
```

`API_PORT` and `WEB_PORT` are for running on your own machine. Coolify assigns
ports itself and ignores them.

---

## 4. Storage — do this before you have anything to lose

The transcripts, the database and the downloaded speech model all live in one
Docker volume, `api-data`, mounted at `/data`. **Without a persistent volume,
every redeploy starts an empty library and re-downloads the model.**

Coolify: **Storages → Add** → volume name `api-data`, mount path `/data`,
attached to the `api` service.

The speech model is roughly 1.5 GB for `large-v3-turbo` and 3 GB for `large-v3`,
on top of the transcripts. Allow 20 GB.

---

## 4b. Which commit is actually running

Open in a browser:

```
https://your-domain/api/meta
```

You get JSON containing `"commit"`. Compare it with the newest commit on the
branch in GitHub. If they differ, the deployment is behind — press Redeploy.
Nothing else in this document matters until those two match.

The same URL answers a second question: if it does not load at all, the domain
is pointed at the `api` service instead of `web`, or the build predates the
`/api` proxy.

---

## 5. Checking it worked

Open the domain. You should get the sign-in screen, then a Dashboard.

Then **Settings → System check**, or from Coolify's terminal on the `api`
container:

```bash
python -m app.cli doctor
```

Read three lines in particular:

- **Sign-in secret** — must not say the shipped default is in use
- **Where audio is processed** — says `faster_whisper` (local) or `sarvam`
  (uploaded to a third party). Both are valid; you should know which
- **Speech-to-text** — names the model actually in force, which is the setting
  people most often believe they changed and did not

---

## 6. When something is wrong

**Site loads, but signing in does nothing, or every screen is empty.**
The browser cannot reach the API. Open the browser console: requests to
`/api/...` should return 200. If they fail, the domain is pointed at `api`
instead of `web`, or `web` was built before the proxy existed — redeploy.

**"Cannot reach the server. Check that the backend is running."**
The `api` container is down or crashed at startup. Read its logs: a missing or
too-short `JWT_SECRET` in production stops it deliberately, and says so.

**Transcription fails on Instagram links.**
Instagram refuses anonymous downloads. Needs a cookie file — see
`docs/COOKIES.md`. YouTube is unaffected.

**Everything is slow.**
Transcription is CPU-bound and shared with everything else on the box. Either
give it more cores, drop `FASTER_WHISPER_MODEL` to `small`, or switch to Sarvam
and let their hardware do it.
