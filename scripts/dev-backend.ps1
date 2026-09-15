# Starts the API for development.
#
# "--reload" means the server restarts automatically whenever a file is saved,
# so you never restart it by hand.
#
#   Usage:  .\scripts\dev-backend.ps1

$ErrorActionPreference = 'Stop'
$root = Split-Path -Parent $PSScriptRoot
$venvPython = Join-Path $root 'backend\.venv\Scripts\python.exe'

if (-not (Test-Path $venvPython)) {
  Write-Host "`n  Backend not set up yet. Run:  .\scripts\setup.ps1`n" -ForegroundColor Yellow
  exit 1
}

Write-Host @'

Starting the API...

  API          http://localhost:8000/api/v1
  Health       http://localhost:8000/api/v1/health
  Interactive  http://localhost:8000/api/v1/docs

Press Ctrl+C to stop.

'@ -ForegroundColor Cyan

Set-Location (Join-Path $root 'backend')
& $venvPython -m uvicorn app.main:app --reload --host 127.0.0.1 --port 8000
