# Deployment

Taking the hub from a laptop to a server people can use.

This describes the supported shape: **one Linux server, Docker Compose,
PostgreSQL, and Caddy terminating HTTPS**. It is what
[`TECH_STACK.md`](TECH_STACK.md) recommends, and it is deliberately boring —
one machine you can reason about, one command to deploy, one file to back up.

---

## What runs

```
                 ┌──────────────────── your server ────────────────────┐
   internet ───► │  caddy  ──┬──► web    (nginx serving the built app)  │
   :80 :443      │           └──► api ──► db  (PostgreSQL)              │
                 └────────────────────────────────────────────────────┘
```

Only Caddy publishes ports. The API and the database are reachable **only** from
inside the Docker network, so a leaked database password is not by itself a way
in from the internet.

Everything is served from one origin: Caddy sends `/api/*` to the backend and
everything else to the static frontend. The browser therefore never makes a
cross-origin request, which removes CORS misconfiguration — a classic cause of
"works locally, broken in production" — from the picture entirely.

---

## Before you start

You need:

| | |
|---|---|
| A server | 4 vCPU / 8 GB RAM is enough when transcribing via Sarvam. See *Sizing* below if you transcribe locally. |
| A domain | With an **A record already pointing at the server's IP**. Caddy cannot obtain a certificate before DNS resolves. |
| Ports 80 and 443 | Open to the internet. Port 80 is required for certificate issuance, not just redirects. |
| Docker Engine + Compose v2 | Docker *Desktop* is not needed on a server, and its licence terms do not apply to Engine. |

### Hosted database instead

To use Supabase (or any hosted PostgreSQL) rather than the database container,
use [`docker-compose.supabase.yml`](../docker-compose.supabase.yml) in place of
`docker-compose.prod.yml` throughout this guide, and follow
[SUPABASE.md](SUPABASE.md) for the connection string. Everything else here —
Caddy, backups, sizing, updating — applies unchanged, except that Supabase takes
over responsibility for database backups.

---

## Deploying

```bash
git clone <your-repo> research-hub && cd research-hub

cp .env.production.example .env.production
```

Now fill in `.env.production`. Every value marked REQUIRED must be set; the
comments in the file explain each one. Generate the two secrets rather than
inventing them:

```bash
python3 -c "import secrets; print(secrets.token_urlsafe(48))"   # JWT_SECRET
python3 -c "import secrets; print(secrets.token_urlsafe(32))"   # POSTGRES_PASSWORD
```

Then:

```bash
docker compose -f docker-compose.prod.yml --env-file .env.production up -d --build
```

The first run takes a few minutes: it builds both images, waits for PostgreSQL
to report healthy, applies the database migrations, creates the first admin
account from `BOOTSTRAP_ADMIN_*`, and asks Let's Encrypt for a certificate.

Watch it happen:

```bash
docker compose -f docker-compose.prod.yml --env-file .env.production logs -f
```

Then open `https://your-domain` and sign in as the bootstrap admin.
**Change that password immediately** — it is sitting in a file on disk.

---

## Updating

```bash
git pull
docker compose -f docker-compose.prod.yml --env-file .env.production up -d --build
```

Migrations run automatically on start and are a no-op when the schema is already
current. Neither container mounts source code — the API image copies it in and
the frontend is a compiled static bundle — so **a code change always requires
`--build`**. Restarting alone silently runs the old version.

### Changing the domain

`VITE_API_BASE_URL` is compiled into the frontend at build time, so changing
`DOMAIN` requires rebuilding `web`, not just restarting it. The command above
already does this.

---

## Backups

```bash
./scripts/backup.sh /var/backups/research-hub
```

Dumps the database and archives the TLS certificates, pruning both after 30
days. Run it from cron:

```cron
0 3 * * * cd /srv/research-hub && ./scripts/backup.sh /var/backups/research-hub
```

The transcripts are the irreplaceable part — the media files are deleted after
transcription by design, and the Whisper model cache re-downloads on demand.

**Restore a dump into a scratch database and read a row out of it before you
need to.** An untested backup is a hope.

---

## Sizing

Transcription is the only demanding workload, and which engine you choose
changes the machine you need by an order of magnitude.

| Engine | Server | Notes |
|---|---|---|
| **Sarvam AI** | 4 vCPU / 8 GB | The work happens on their hardware. Costs money per minute of audio beyond the free allowance, and the audio is uploaded to a third party. |
| **Local (faster-whisper)** | 8–16 vCPU / 16 GB | Free and nothing leaves the server, but `large-v3` runs roughly 0.5× realtime on 16 cores and slower on fewer. |

`WORKER_CONCURRENCY` is the number of videos processed at once. With local
transcription keep it at or below `cores / 4`; above that, jobs compete for the
same CPU and everything gets slower rather than more parallel.

Local transcription also needs disk for the model cache — around 3 GB for
`large-v3`. It lives on the `api-data` volume so it survives rebuilds.

---

## Operational realities

**Instagram and YouTube will fight you.** Reels require a cookies file (see
[COOKIES.md](COOKIES.md)), those cookies expire, and datacenter IP ranges are
blocked far more aggressively than home connections. Expect this to be the main
recurring maintenance task, and expect it to be worse on a server than it was on
your laptop. `COOKIES_FILE` must point at a path inside the container — put the
file on the `api-data` volume.

**The limits are your cost ceiling.** `MAX_VIDEO_DURATION_SECONDS`,
`MAX_VIDEO_FILESIZE_BYTES` and `MAX_URLS_PER_REQUEST` bound what a single
submission can cost you in CPU time or Sarvam credit. The production defaults
are tighter than the development ones for that reason.

**Logs grow.** Docker's default json-file driver has no size limit. Add one in
`/etc/docker/daemon.json` before the disk fills:

```json
{ "log-driver": "json-file", "log-opts": { "max-size": "10m", "max-file": "3" } }
```

---

## Not yet suitable for public signup

This setup is production-ready for a **known set of users whose accounts an
admin creates**. It is *not* ready to be opened to public registration, and the
gap is not configuration:

| Missing | Why it matters |
|---|---|
| Registration flow | There is no public signup endpoint. Accounts are created by an admin (`POST /api/auth/users`) or the CLI. |
| Email verification | Nothing sends email, so addresses cannot be confirmed. |
| Per-user quotas | Nothing caps how much any one account transcribes. With Sarvam, that is your money; with local transcription, it is your CPU. |
| Rate limiting | No limit on requests, including on `/api/auth/login`, which is what makes password guessing slow. |
| Abuse handling | No way to suspend an account mid-abuse beyond deleting it. |

Opening registration without at least quotas and rate limiting means strangers
spending your Sarvam allowance. Treat the table above as the prerequisite list,
not a wishlist.

There is also a question worth answering deliberately rather than by default: a
private tool that downloads platform content for a team's own research is a very
different proposition, legally and in terms of platform enforcement, from a
public service that does it for anyone who signs up.
