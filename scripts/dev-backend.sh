#!/usr/bin/env bash
#
# Starts the API for development. `--reload` restarts it whenever a file is
# saved, so you never restart it by hand.
#
#   Usage:  bash scripts/dev-backend.sh

set -euo pipefail

ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
VENV_PYTHON="$ROOT/backend/.venv/bin/python"

if [ ! -x "$VENV_PYTHON" ]; then
  printf '\n\033[33m  Backend not set up yet. Run:  bash scripts/setup.sh\033[0m\n\n' >&2
  exit 1
fi

printf '\033[36m
Starting the API...

  API          http://localhost:8000/api/v1
  Health       http://localhost:8000/api/v1/health
  Interactive  http://localhost:8000/api/v1/docs

Press Ctrl+C to stop.
\033[0m\n'

cd "$ROOT/backend"
exec "$VENV_PYTHON" -m uvicorn app.main:app --reload --host 127.0.0.1 --port 8000
