# Putting the database on Supabase

A step-by-step guide, starting from having no Supabase account at all.

---

## First, what is happening here

Right now your app keeps its data in a file on your own computer. That works
while you are the only person using it. To put the app on the internet for other
people, the data needs to live somewhere that is always on. Supabase is that
somewhere.

**Supabase is a database that lives on the internet.** A database is just an
organised way to store information — think of a spreadsheet file, but one that
many people can safely use at the same time.

**Tables are like the sheets inside a spreadsheet.** Your app needs seven:

| Table | What it holds |
|---|---|
| `users` | People who can log in |
| `videos` | The reels and videos you submitted |
| `transcripts` | The text of what was said |
| `transcript_segments` | That text, split up by timestamp |
| `jobs` | Which videos are being processed right now |
| `app_settings` | Your choices from the Settings page |
| `alembic_version` | A bookmark — explained in Step 4 |

**You do not design any of these.** You do not choose columns, or types, or
decide what goes in them. The app already knows exactly what it needs, and can
build all seven itself. Your job in this guide is to create a Supabase project
and copy one line of text. That is genuinely all.

---

## Step 1 — Make a Supabase account and project

1. Go to [supabase.com](https://supabase.com) and sign up.
2. Click **New project**.
3. Fill in three things:

   **Name** — anything you like, for example `research-hub`.

   **Database Password** — click *Generate a password*, then **copy it into your
   password manager before you do anything else**. Supabase will not show you
   this password again. You need it in Step 2. If you lose it you have to reset
   it, which is annoying but not fatal.

   **Region** — this is where the database physically sits. Choose the one
   closest to *the server that will run your app*, not the one closest to you.
   Every time the app reads or writes data, the request travels this distance.
   If your app will run on a server in India, choose `ap-south-1 (Mumbai)`.

4. Click Create, then wait about two minutes while Supabase builds it.

---

## Step 2 — Find your connection string

A connection string is one line of text that tells the app **where the database
is and how to log into it**. It is like an address and a key combined.

1. In your project, click **Project Settings** (the gear icon at the bottom
   left), then **Database**.
2. Scroll to **Connection string**.
3. You will see three tabs. **Choose the one called "Session pooler".**

   This matters, and here is why — the other two genuinely do not work here:

   | Tab | Use it? |
   |---|---|
   | **Session pooler** | **Yes, this one.** Works everywhere, and supports the way this app talks to the database. |
   | Direct connection | Only works if your server has IPv6, which most do not. |
   | Transaction pooler | Looks similar, but breaks this app in confusing, intermittent ways. |

4. Copy the line. It looks something like this:

   ```
   postgresql://postgres.abcdefghijkl:[YOUR-PASSWORD]@aws-0-ap-south-1.pooler.supabase.com:5432/postgres
   ```

---

## Step 3 — Adjust the connection string

Supabase gives you a general-purpose version of this line. Your app needs three
small changes to it. All three are required — miss one and it will not connect.

**Change 1 — say which driver to use.**

A driver is the piece of software that actually talks to the database. Change
the very beginning:

```
postgresql://          ←  what Supabase gives you
postgresql+asyncpg://  ←  what you want
```

**Change 2 — put your real password in.**

Replace `[YOUR-PASSWORD]` (including the square brackets) with the password you
saved in Step 1.

There is a catch. The password sits inside a web address, and a few characters
mean something special in a web address. If your password contains any of these,
it will break the line unless you replace it:

| If your password has | Write this instead |
|---|---|
| `@` | `%40` |
| `#` | `%23` |
| `/` | `%2F` |
| `:` | `%3A` |
| `?` | `%3F` |
| `%` | `%25` |

The easiest way to avoid this entirely is to use a password with only letters
and numbers. If yours has symbols, this command converts it for you:

```bash
python3 -c "import urllib.parse,getpass; print(urllib.parse.quote(getpass.getpass('Password: '), safe=''))"
```

**Change 3 — turn on encryption.**

Supabase refuses connections that are not encrypted. Add this to the very end:

```
?ssl=require
```

**The finished line looks like this:**

```
postgresql+asyncpg://postgres.abcdefghijkl:YourPassword@aws-0-ap-south-1.pooler.supabase.com:5432/postgres?ssl=require
```

### Put it in the settings file

On the computer or server that will run the app:

```bash
cp .env.production.example .env.production
```

Open `.env.production` in a text editor and:

- Set `DATABASE_URL=` to your finished line from above.
- Leave `POSTGRES_PASSWORD`, `POSTGRES_DB` and `POSTGRES_USER` **empty** — those
  are only used if you run your own database instead of Supabase.
- Fill in the other values marked REQUIRED: `JWT_SECRET`, `DOMAIN`,
  `ACME_EMAIL`, `BOOTSTRAP_ADMIN_EMAIL`, `BOOTSTRAP_ADMIN_PASSWORD` and
  `SARVAM_API_KEY`.

This file now contains your database password. It is already in `.gitignore`, so
it will not be uploaded to GitHub — but do not email it or paste it anywhere.

---

## Step 4 — Create the seven tables

Here are both ways. **They produce exactly the same result.** Pick one.

| | **Method A — one command** | **Method B — paste SQL** |
|---|---|---|
| What you do | Run one line in the terminal | Paste text into the Supabase website |
| Where you do it | On your computer or server | In your browser |
| Can you watch it happen? | Yes, in the terminal output | Yes, on screen |
| **When the app updates later** | **Run the same command. It adds only what is new.** | **You must write and paste new SQL by hand, every time.** |

That last row is the only real difference, and it is worth understanding before
you choose.

### About that bookmark

Remember `alembic_version` from the table list? It holds one short line of text,
and its whole job is to record **how far the database has been built**.

Say in two months the app needs a new column — for example, "who deleted this
video". With Method A, you run the same command again; it reads the bookmark,
sees that new column is missing, and adds just that. It never redoes work.

Without the bookmark, nothing knows what has already been done.

### Method A — one command

```bash
docker compose -f docker-compose.supabase.yml --env-file .env.production build api
docker compose -f docker-compose.supabase.yml --env-file .env.production run --rm api python -m app.cli migrate
```

You should see:

```
INFO  [alembic.runtime.migration] Running upgrade  -> fc77b2bb710f, initial schema
Database schema upgraded.
```

That is it. All seven tables now exist, bookmark included.

If it fails instead, the message will match a row in *Troubleshooting* at the
bottom of this page — each one tells you which of the three changes in Step 3
was missed.

### Method B — paste SQL

1. Open [`scripts/schema.sql`](../scripts/schema.sql) in a text editor.
2. Select all of it and copy it.
3. In Supabase, click **SQL Editor** in the left sidebar, then **New query**.
4. Paste, and click **Run**.

**Copy the whole file, including the line near the end that begins
`INSERT INTO alembic_version`.** That line writes the bookmark. It is easy to
mistake for leftover noise and leave out. Without it, the app will later try to
create these same tables a second time and fail with an error saying they
already exist.

The whole thing is wrapped in `BEGIN` and `COMMIT`, which means it either fully
works or fully undoes itself. You cannot end up with half the tables.

> **Which would I choose?** Method A, because you only learn one command and it
> keeps working forever. But Method B is a perfectly reasonable way to see it
> happen with your own eyes, and afterwards both leave you in exactly the same
> place.

---

## Step 5 — Start the app

```bash
docker compose -f docker-compose.supabase.yml --env-file .env.production up -d --build
```

The first run takes a few minutes — it builds the app, connects to Supabase,
creates your admin account, and requests a security certificate for your domain.

Watch it happen:

```bash
docker compose -f docker-compose.supabase.yml --env-file .env.production logs -f
```

Then open `https://your-domain` in a browser and sign in with the
`BOOTSTRAP_ADMIN_EMAIL` and `BOOTSTRAP_ADMIN_PASSWORD` you set.

**Change that password straight away.** It is written in a file on the server.

---

## How to check it actually worked

**In Supabase:** click **Table Editor** in the sidebar. You should see all seven
tables. Click `users` — there should be exactly one row, your admin account.
That row is proof the app wrote to Supabase successfully.

**You will see orange "RLS disabled" warnings. Ignore them.** RLS (Row Level
Security) protects a different Supabase feature — an automatic web API that this
app does not use. Your app connects directly and checks permissions in its own
code. Turning RLS on would add no protection here and would only confuse things
later.

**From the command line**, this should say `"database": true`:

```bash
curl https://your-domain/api/health
```

---

## Things that will catch you out

**Free projects go to sleep.** On the free plan, Supabase pauses a project after
7 days without activity. A paused project refuses connections, so your site goes
down until somebody logs in and clicks Restore. That is fine while you are
testing. It is not acceptable once real people depend on it — that alone is
usually the reason to move to a paid plan.

**Search becomes less good.** On your laptop the app uses a proper full-text
search index. On Supabase it falls back to simple "does this text contain those
words" matching ([`search.py:330`](../backend/app/services/search.py#L330)). It
still finds things, but it does not rank results by relevance, and it gets
slower as you collect more transcripts. This is fixable later; it is not urgent.

**Backups are now Supabase's job, not yours.** The
[`scripts/backup.sh`](../scripts/backup.sh) script backs up a database running on
your own server, so it no longer covers your data. Check what your Supabase plan
actually keeps and for how long — free-tier retention is short. Your transcripts
are the one thing you cannot recreate.

**Everything is slightly slower.** A database on the same machine answers
instantly. Supabase is somewhere else in the world, so every request makes a
round trip. You will not notice it reading one transcript. You may notice it on
pages that ask many small questions at once.

---

## Troubleshooting

| What you see | What it means |
|---|---|
| `ModuleNotFoundError: No module named 'psycopg2'` | The line still starts with `postgresql://`. It must be `postgresql+asyncpg://` — Change 1. |
| `rejected SSL upgrade` or `SSL required` | `?ssl=require` is missing from the end — Change 3. |
| `password authentication failed` | Usually a symbol in the password that was not converted — Change 2. |
| `Network is unreachable` | You used the Direct connection tab on a server without IPv6. Use Session pooler. |
| `prepared statement "__asyncpg_stmt_1__" already exists` | You used the Transaction pooler tab. Use Session pooler. |
| `relation "users" already exists` | The tables were created twice — most likely Method B was used without the final `INSERT INTO alembic_version` line. |
| Worked for days, then `Connection refused` | A free-tier project went to sleep. Open the dashboard and restore it. |
