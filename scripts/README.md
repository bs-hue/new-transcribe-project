# scripts/

One-command helpers, so day-to-day work never requires remembering a sequence
of commands. All are safe to re-run.

## Use these (Linux / WSL — the supported environment)

| Script | What it does |
|---|---|
| `setup.sh` | Full first-time setup: finds Python 3.12, creates the virtual environment, installs backend and frontend dependencies, creates `.env` from the template, and warns about missing optional tools. Never overwrites an existing `.env`. |
| `dev-backend.sh` | Starts the API on port 8000 with auto-reload on save. |
| `dev-frontend.sh` | Starts the website on port 5173, forwarding `/api` to the backend. |

```bash
bash scripts/setup.sh
```

Invoke with `bash scripts/...` rather than `./scripts/...` — the execute bit is
not preserved on files stored on a Windows drive.

## The `.ps1` versions

The PowerShell scripts are the same steps for **Windows-native** development. They
are kept for machines where that works, but they will fail wherever **Smart App
Control** is enabled: it blocks the unsigned compiled libraries that both the API
(`pydantic_core`) and the frontend toolchain (`rollup`) depend on. That is a
Windows security policy, not a bug we can fix — hence WSL.

If you do use them and PowerShell refuses to run scripts, allow local scripts once:

```powershell
Set-ExecutionPolicy -Scope CurrentUser RemoteSigned
```
