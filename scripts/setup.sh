#!/usr/bin/env bash
#
# First-time setup for Linux / WSL — the supported development environment for
# this project.
#
# Safe to re-run: it skips work already done and never overwrites your .env.
#
#   Usage:  bash scripts/setup.sh

set -euo pipefail

ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"

step() { printf '\n\033[36m=== %s ===\033[0m\n' "$1"; }
ok() { printf '  \033[32mOK\033[0m  %s\n' "$1"; }
skip() { printf '  --  %s\n' "$1"; }
warn() { printf '  \033[33m!\033[0m   %s\n' "$1"; }
die() {
  printf '\n\033[31m%s\033[0m\n\n' "$1" >&2
  exit 1
}

# ── 1. Python ───────────────────────────────────────────────────────────────
# 3.11 or 3.12 specifically: newer releases lack prebuilt packages for the
# Phase 2 transcription stack. Ubuntu 24.04 ships 3.12, so this normally
# succeeds with no extra installation.
step 'Locating Python 3.12'

PYTHON=""
for candidate in python3.12 python3.11; do
  if command -v "$candidate" >/dev/null 2>&1; then
    PYTHON="$candidate"
    break
  fi
done

if [ -z "$PYTHON" ]; then
  die "Python 3.12 not found. Install it with:

  sudo apt update && sudo apt install -y python3.12 python3.12-venv"
fi
ok "Using $("$PYTHON" --version)"

# ── 2. Virtual environment ──────────────────────────────────────────────────
# A private folder of libraries for this project alone, so it cannot conflict
# with anything else on the system.
step 'Backend virtual environment'

VENV="$ROOT/backend/.venv"
if [ -x "$VENV/bin/python" ]; then
  skip 'Already exists (delete backend/.venv to rebuild)'
else
  "$PYTHON" -m venv "$VENV" 2>/dev/null || die "Could not create the virtual environment.
The venv module is packaged separately on Debian/Ubuntu:

  sudo apt install -y ${PYTHON}-venv"
  ok 'Created backend/.venv'
fi

# ── 3. Backend dependencies ─────────────────────────────────────────────────
step 'Installing backend dependencies'

"$VENV/bin/python" -m pip install --upgrade pip --quiet
(cd "$ROOT/backend" && "$VENV/bin/python" -m pip install -e ".[dev]" --quiet)
ok 'Backend ready'

# ── 4. Frontend dependencies ────────────────────────────────────────────────
step 'Installing frontend dependencies'

command -v npm >/dev/null 2>&1 || die "npm not found. Install Node.js 20 or newer:

  curl -fsSL https://deb.nodesource.com/setup_22.x | sudo -E bash -
  sudo apt install -y nodejs"

(cd "$ROOT/frontend" && npm install --no-fund --no-audit)
ok 'Frontend ready'

# ── 5. Configuration ────────────────────────────────────────────────────────
step 'Configuration file'

if [ -f "$ROOT/.env" ]; then
  skip '.env already exists — left untouched'
else
  cp "$ROOT/.env.example" "$ROOT/.env"
  ok 'Created .env from .env.example'
fi

# ── 6. Optional tooling used from Phase 2 onward ─────────────────────────────
step 'Checking optional tools'

if command -v ffmpeg >/dev/null 2>&1; then
  ok "ffmpeg present ($(ffmpeg -version | head -n 1 | cut -d' ' -f1-3))"
else
  warn 'ffmpeg not installed — needed from Phase 2: sudo apt install -y ffmpeg'
fi

# Working from a Windows drive inside WSL means file-change events are
# unreliable, so hot reload can silently stop working.
if [[ "$ROOT" == /mnt/* ]]; then
  warn "Project is on a Windows drive ($ROOT)."
  warn 'If the browser stops auto-reloading, start the frontend with:'
  warn '  VITE_USE_POLLING=true bash scripts/dev-frontend.sh'
fi

printf '\n\033[32mSetup complete. Start the app in two terminals:

  bash scripts/dev-backend.sh     ->  http://localhost:8000
  bash scripts/dev-frontend.sh    ->  http://localhost:5173

Then open http://localhost:5173\033[0m\n\n'
