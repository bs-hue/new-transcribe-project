# Starts the website for development.
#
# The page reloads instantly when you save a file. Requests to /api are
# forwarded to the backend on port 8000, so both sides work together.
#
#   Usage:  .\scripts\dev-frontend.ps1

$ErrorActionPreference = 'Stop'
$root = Split-Path -Parent $PSScriptRoot

if (-not (Test-Path (Join-Path $root 'frontend\node_modules'))) {
  Write-Host "`n  Frontend not set up yet. Run:  .\scripts\setup.ps1`n" -ForegroundColor Yellow
  exit 1
}

Write-Host @'

Starting the website...

  http://localhost:5173

Requests to /api are forwarded to the backend on port 8000,
so start dev-backend.ps1 in another terminal too.

Press Ctrl+C to stop.

'@ -ForegroundColor Cyan

Set-Location (Join-Path $root 'frontend')
& npm run dev
