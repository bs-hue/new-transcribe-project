#!/usr/bin/env bash
#
# Starts the website for development. Requests to /api are forwarded to the
# backend on port 8000, so both sides work together.
#
#   Usage:  bash scripts/dev-frontend.sh
#
# If the browser stops reloading on save (common when the project sits on a
# Windows drive accessed from WSL), enable polling:
#
#   VITE_USE_POLLING=true bash scripts/dev-frontend.sh

set -euo pipefail

ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"

if [ ! -d "$ROOT/frontend/node_modules" ]; then
  printf '\n\033[33m  Frontend not set up yet. Run:  bash scripts/setup.sh\033[0m\n\n' >&2
  exit 1
fi

printf '\033[36m
Starting the website...

  http://localhost:5173

Requests to /api go to the backend on port 8000,
so run dev-backend.sh in another terminal too.

Press Ctrl+C to stop.
\033[0m\n'

cd "$ROOT/frontend"
exec npm run dev
