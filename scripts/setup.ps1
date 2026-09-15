# Sets up everything needed to develop locally, in the right order.
#
# Safe to re-run: it skips work that's already done and never overwrites
# your .env file.
#
#   Usage:  .\scripts\setup.ps1

$ErrorActionPreference = 'Stop'
$root = Split-Path -Parent $PSScriptRoot

function Write-Step($text) { Write-Host "`n=== $text ===" -ForegroundColor Cyan }
function Write-Ok($text)   { Write-Host "  OK  $text" -ForegroundColor Green }
function Write-Skip($text) { Write-Host "  --  $text" -ForegroundColor DarkGray }

# ── 1. Find a supported Python ────────────────────────────────────────────
# We need 3.11 or 3.12. Newer versions don't yet have prebuilt packages for
# the transcription libraries we'll add in Phase 2.
Write-Step 'Locating Python 3.12'

$python = $null
foreach ($version in @('3.12', '3.11')) {
  try {
    $candidate = & py "-$version" -c "import sys; print(sys.executable)" 2>$null
    if ($LASTEXITCODE -eq 0 -and $candidate) { $python = $candidate.Trim(); break }
  } catch { }
}

if (-not $python) {
  Write-Host @'

  Python 3.12 was not found.

  Install it with:      winget install Python.Python.3.12
  Or download from:     https://www.python.org/downloads/
                        (tick "Add python.exe to PATH" during install)

  Any Python you already have stays installed and untouched.

'@ -ForegroundColor Yellow
  exit 1
}
Write-Ok "Using $python"

# ── 2. Create the virtual environment ─────────────────────────────────────
# A "virtual environment" is a private folder of libraries for THIS project,
# so it can never conflict with anything else on your machine.
Write-Step 'Backend virtual environment'

$venv = Join-Path $root 'backend\.venv'
$venvPython = Join-Path $venv 'Scripts\python.exe'

if (Test-Path $venvPython) {
  Write-Skip 'Already exists (delete backend\.venv to rebuild)'
} else {
  & $python -m venv $venv
  Write-Ok 'Created backend\.venv'
}

# ── 3. Install backend dependencies ───────────────────────────────────────
Write-Step 'Installing backend dependencies'

& $venvPython -m pip install --upgrade pip --quiet
Push-Location (Join-Path $root 'backend')
try {
  & $venvPython -m pip install -e ".[dev]" --quiet
  if ($LASTEXITCODE -ne 0) { throw 'Backend dependency installation failed.' }
} finally {
  Pop-Location
}
Write-Ok 'Backend ready'

# ── 4. Install frontend dependencies ──────────────────────────────────────
Write-Step 'Installing frontend dependencies'

Push-Location (Join-Path $root 'frontend')
try {
  & npm install --no-fund --no-audit
  if ($LASTEXITCODE -ne 0) { throw 'Frontend dependency installation failed.' }
} finally {
  Pop-Location
}
Write-Ok 'Frontend ready'

# ── 5. Create .env from the template ──────────────────────────────────────
Write-Step 'Configuration file'

$envFile = Join-Path $root '.env'
if (Test-Path $envFile) {
  Write-Skip '.env already exists — left untouched'
} else {
  Copy-Item (Join-Path $root '.env.example') $envFile
  Write-Ok 'Created .env from .env.example'
}

# ── Done ──────────────────────────────────────────────────────────────────
Write-Host @'

Setup complete. Start the app in two separate terminals:

  .\scripts\dev-backend.ps1     ->  http://localhost:8000
  .\scripts\dev-frontend.ps1    ->  http://localhost:5173

Then open http://localhost:5173

'@ -ForegroundColor Green
