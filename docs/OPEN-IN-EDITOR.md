# Opening this project in Antigravity (or VS Code / Cursor / Windsurf)

Antigravity is Google's AI coding editor. It is built on VS Code, so are Cursor
and Windsurf — which means all of them read the same project setup files, and
these steps work identically in any of them.

The project ships with its own editor configuration (`.vscode/`), so most of the
setup happens automatically when you open it.

---

## Before you start

`main` contains the whole project, so a normal clone gets everything. Nothing
special to do.

<details>
<summary>If the folder looks empty after cloning</summary>

This used to happen when `main` was still an empty starting point and the code
lived on a feature branch. It shouldn't now — but if you do land on an empty
folder, you are on the wrong branch rather than looking at a broken repository.

Click the branch name in the **bottom-left corner** of the editor and pick
`main`, or from a terminal:

```bash
git checkout main && git pull
```

</details>

---

## Step 1 — Get the project onto your computer

**In the editor:**

1. Open Antigravity.
2. From the welcome screen, choose **Clone Git Repository**.
   (If you don't see it: press `Ctrl+Shift+P` / `Cmd+Shift+P` to open the
   Command Palette, type `git clone`, and pick **Git: Clone**.)
3. Paste this address:
   ```
   https://github.com/bs-hue/bulk-transcript-agent.git
   ```
4. Choose a folder to keep it in — Documents is fine.
5. When it asks whether to open the cloned repository, say **yes**.

**Or from a terminal**, if you prefer:

```bash
git clone https://github.com/bs-hue/bulk-transcript-agent.git
cd bulk-transcript-agent
```

You may be asked to sign in to GitHub. That's expected — it's a private
repository.

---

## Step 2 — Check you're looking at the project

The file tree on the left should show `backend`, `frontend` and `docs`. If it
does, you're in the right place — carry on.

If it's empty, see the note at the top of this page.

---

## Step 3 — Say yes to the extension prompt

A notification will appear in the bottom-right: *"This workspace has extension
recommendations."* Click **Install All**.

These add Python and TypeScript support so the editor understands the code and
can help you. They're all free. Nothing breaks if you skip it — the app still
runs — but the editor will be less useful.

---

## Step 4 — Create your settings file

The project needs a file called `.env` holding your own settings. It isn't in
the repository, because it holds passwords.

1. In the file tree, find `.env.example`.
2. Right-click it → **Copy**, then right-click the empty space → **Paste**.
3. Rename the copy to exactly `.env` (no `.example`).
4. Open it and fill in three lines:

```
BOOTSTRAP_ADMIN_EMAIL=you@youragency.com
BOOTSTRAP_ADMIN_PASSWORD=pick-something-long
JWT_SECRET=any-long-random-string-at-least-40-characters-long
```

Everything else can stay as it is. In particular, leave the transcription
settings alone — local, free transcription is already the default.

---

## Step 5 — Install and check, using the built-in tasks

The project comes with ready-made tasks so you don't have to type commands.

Open the Command Palette (`Ctrl+Shift+P` / `Cmd+Shift+P`), type
**`Run Task`**, and press Enter. You'll see this list:

| Task | What it does |
|---|---|
| **Setup: install everything** | Run this once. Installs both halves of the app. Takes a few minutes. |
| **Check: can this machine run it?** | ⭐ The important one. Downloads the speech model and transcribes a test clip. |
| **Create my login** | Makes your admin account. Prompts for a password. |
| **Run: the whole app** | Starts everything. Then open http://localhost:5173 |
| **Test: backend** | Runs all 144 automated checks. |
| **Test: frontend build** | Confirms the website builds cleanly. |

**Run them in that order.** After "Check: can this machine run it?" you should
see:

```
Everything checks out. You are ready to add videos.
```

If instead you get a `FAIL` line, it comes with a specific instruction for
fixing it. Send me what it says and I'll tell you what to do.

### Before you can install anything

The tasks need two free tools on your computer first:

| Tool | Why | Where |
|---|---|---|
| **Python 3.11+** | Runs the engine | [python.org](https://python.org) |
| **Node 20+** | Builds the website | [nodejs.org](https://nodejs.org) |
| **FFmpeg** | Extracts audio from video | [ffmpeg.org](https://ffmpeg.org) — Mac: `brew install ffmpeg` |

If you'd rather not install these, use Docker instead — it bundles all three.
See [`SETUP.md`](SETUP.md).

---

## Step 6 — Run it

Command Palette → **Run Task** → **Run: the whole app**.

Two panels open at the bottom showing the engine and the website starting up.
Then open **http://localhost:5173** in a browser and sign in with the email and
password from your `.env`.

To stop: click the bin icon on those terminal panels.

---

## Using the AI assistant on this project

Antigravity's assistant reads the project as it works. Some things worth knowing:

- **Point it at the docs.** [`TECHNICAL_ARCHITECTURE.md`](TECHNICAL_ARCHITECTURE.md) explains how
  the pieces fit and where new features are meant to attach. Asking it to read
  that first produces much better answers than asking cold.
- **`docs/TECH_STACK.md`** records *why* each technology was chosen. If the
  assistant suggests replacing something, that file usually already covers
  whether the alternative was considered and rejected.
- **Keep the free-first rule explicit.** If you ask for new features, say "no
  paid APIs" in the request — otherwise assistants tend to reach for a paid
  service by default. That is exactly the mistake I made on the first pass.
- **Run the tests after any AI-made change.** Command Palette → Run Task →
  **Test: backend**. 144 checks take about 40 seconds and will catch most
  breakage immediately.

---

## Common problems

| What you see | Why | Fix |
|---|---|---|
| Folder looks empty after cloning | You're on an old feature branch, not `main` | `git checkout main && git pull` |
| "Python interpreter not found" | Setup task hasn't run yet | Run **Setup: install everything**, then reload the window |
| Red squiggles under `import` lines | Editor hasn't found the project's Python | Command Palette → **Python: Select Interpreter** → pick the one inside `backend/.venv` |
| Tasks list is empty | Wrong folder is open | Open the folder containing `backend`, `frontend` and `docs` — not one of them |
| Terminal says `ffmpeg: command not found` | FFmpeg isn't installed | See the table in Step 5 |
| Port already in use | Something else is on 8000 or 5173 | Stop the other program, or change the port in the task |

---

## If any of this doesn't match what you see

Antigravity is a young product and its menus may have moved since this was
written. The underlying steps do not change: **clone → switch branch → install →
check → run**. Any VS Code instructions you find online will apply.

Tell me what you're actually seeing on screen and I'll work it out with you.
