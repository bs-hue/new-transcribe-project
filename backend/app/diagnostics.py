"""Self-checks — "is this machine actually able to run the hub?"

Exists because the failure modes here are environmental, not logical: ffmpeg
missing, the speech model not downloaded, a database directory that is not
writable. Those produce confusing errors halfway through a job. This finds them
up front and says so in plain English.

Run with:  python -m app.cli doctor
"""

from __future__ import annotations

import asyncio
import shutil
import sys
import time
from dataclasses import dataclass, field
from pathlib import Path

from app.config import Settings, get_settings

#: Bundled 3-second speech clip. Lets the deepest check prove the whole
#: audio → text chain end to end rather than only that the model loads.
#: Inside the app package (not tests/) so it ships in the Docker image too.
SAMPLE_AUDIO = Path(__file__).resolve().parent / "assets" / "speech_sample.mp3"
SAMPLE_EXPECTED_WORDS = ("hook", "first", "three", "seconds", "video")


@dataclass
class CheckResult:
    name: str
    ok: bool
    detail: str
    #: Set when the check failed and there is a concrete thing to do about it.
    fix: str | None = None
    #: True when a failure is survivable — the app runs, just not this part.
    warning_only: bool = False


@dataclass
class Report:
    results: list[CheckResult] = field(default_factory=list)

    @property
    def failures(self) -> list[CheckResult]:
        return [r for r in self.results if not r.ok and not r.warning_only]

    @property
    def warnings(self) -> list[CheckResult]:
        return [r for r in self.results if not r.ok and r.warning_only]

    @property
    def ok(self) -> bool:
        return not self.failures


# --- individual checks -------------------------------------------------------


def check_python() -> CheckResult:
    version = f"{sys.version_info.major}.{sys.version_info.minor}.{sys.version_info.micro}"
    ok = sys.version_info >= (3, 11)
    return CheckResult(
        name="Python version",
        ok=ok,
        detail=f"Python {version}",
        fix=None if ok else "This project needs Python 3.11 or newer.",
    )


def check_binary(binary: str, label: str) -> CheckResult:
    path = shutil.which(binary)
    return CheckResult(
        name=label,
        ok=path is not None,
        detail=path or "not found on PATH",
        fix=(
            None
            if path
            else f"Install ffmpeg, which provides {binary}. "
            "macOS: brew install ffmpeg · Ubuntu: sudo apt install ffmpeg · "
            "Windows: download from ffmpeg.org"
        ),
    )


def check_work_dir(settings: Settings) -> CheckResult:
    try:
        work_dir = settings.resolved_work_dir()
        probe = work_dir / ".write-test"
        probe.write_text("ok", encoding="utf-8")
        probe.unlink()
        return CheckResult(name="Working folder", ok=True, detail=f"{work_dir} (writable)")
    except OSError as exc:
        return CheckResult(
            name="Working folder",
            ok=False,
            detail=str(exc),
            fix=f"Make {settings.work_dir} writable by the user running the app.",
        )


def check_jwt_secret(settings: Settings) -> CheckResult:
    from app.core.security import INSECURE_DEFAULT_SECRET

    is_default = settings.jwt_secret == INSECURE_DEFAULT_SECRET
    too_short = len(settings.jwt_secret) < 32
    development = settings.environment == "development"

    if not (is_default or too_short):
        return CheckResult(name="Sign-in secret", ok=True, detail="set and long enough")

    problem = "still the shipped default" if is_default else "shorter than 32 characters"
    return CheckResult(
        name="Sign-in secret",
        ok=False,
        warning_only=development,
        detail=f"JWT_SECRET is {problem}"
        + (" (allowed in development)" if development else ""),
        fix="Set JWT_SECRET in .env to a long random value. Generate one with: "
        'python -c "import secrets; print(secrets.token_urlsafe(48))"',
    )


def check_no_paid_api(settings: Settings | None = None) -> CheckResult:
    """Says plainly whether audio leaves this machine.

    A hosted provider is available and is a legitimate choice — it is far faster
    on Indian languages than anything a CPU can run. It also means client audio
    is uploaded to a third party, which reverses a promise made in Version 1.
    So the check reports what is *configured*, not what is *installed*: whoever
    reads this report is entitled to know which of the two they are running.
    """
    from app.services.transcription import LOCAL_PROVIDERS

    settings = settings or get_settings()
    configured = settings.transcription_provider.strip().lower()
    local = configured in LOCAL_PROVIDERS

    return CheckResult(
        name="Where audio is processed",
        ok=True,  # both answers are valid; neither is a failure
        warning_only=not local,
        detail=(
            f"{configured} — on this machine. Nothing is uploaded and nothing is charged."
            if local
            else f"{configured} — audio is uploaded to a third party for transcription."
        ),
        fix=(
            None
            if local
            else "Client audio leaves your network. Set TRANSCRIPTION_PROVIDER="
            "faster_whisper to keep it local."
        ),
    )


async def check_database(settings: Settings) -> CheckResult:
    from app.db.session import healthcheck, init_db

    try:
        await init_db(settings)
        ok = await healthcheck()
        kind = "SQLite" if settings.is_sqlite else "external database"
        return CheckResult(
            name="Database",
            ok=ok,
            detail=f"{kind} reachable" if ok else "could not be reached",
            fix=None if ok else "Check DATABASE_URL in .env.",
        )
    except Exception as exc:
        return CheckResult(
            name="Database",
            ok=False,
            detail=str(exc),
            fix="Check DATABASE_URL in .env, and that the folder is writable.",
        )


async def check_transcription(settings: Settings, *, deep: bool) -> list[CheckResult]:
    """Load the speech model and, when ``deep``, transcribe the bundled sample.

    Model load is the slow, network-dependent step — it downloads ~150 MB the
    first time. Doing it here means the first real video is not where someone
    discovers their machine cannot reach the model host.
    """
    from app.core.errors import AppError
    from app.services.transcription import get_transcription_provider

    results: list[CheckResult] = []

    try:
        provider = get_transcription_provider(settings)
        provider.validate_configuration()
    except AppError as exc:
        return [
            CheckResult(
                name="Speech-to-text",
                ok=False,
                detail=exc.message,
                fix="Run: pip install faster-whisper",
            )
        ]

    from app.services.transcription import LOCAL_PROVIDERS

    where = "runs locally, free" if provider.name in LOCAL_PROVIDERS else "hosted service"
    results.append(
        CheckResult(
            name="Speech-to-text",
            ok=True,
            detail=f"{provider.name} · model '{provider.model_name}' · {where}",
        )
    )

    if not deep:
        results.append(
            CheckResult(
                name="Transcription self-test",
                ok=True,
                detail="skipped (run with --deep to download the model and test for real)",
            )
        )
        return results

    if not SAMPLE_AUDIO.exists():
        results.append(
            CheckResult(
                name="Transcription self-test",
                ok=False,
                warning_only=True,
                detail=f"sample clip missing at {SAMPLE_AUDIO}",
                fix="Re-clone the repository; the sample ships with it.",
            )
        )
        return results

    started = time.monotonic()
    try:
        result = await provider.transcribe(SAMPLE_AUDIO)
    except AppError as exc:
        results.append(
            CheckResult(
                name="Transcription self-test",
                ok=False,
                detail=exc.message,
                fix="The speech model is downloaded on first use. Check this machine "
                "can reach huggingface.co, then try again.",
            )
        )
        return results

    elapsed = time.monotonic() - started
    text = result.text.strip()
    heard = [word for word in SAMPLE_EXPECTED_WORDS if word in text.lower()]
    good = len(heard) >= 3

    # 3.6 s of audio; the ratio is a rough but honest speed signal for this box.
    speed = 3.6 / elapsed if elapsed > 0 else 0
    results.append(
        CheckResult(
            name="Transcription self-test",
            ok=good,
            warning_only=not good,
            detail=f'heard "{text}" in {elapsed:.1f}s ({speed:.1f}x realtime)',
            fix=None
            if good
            else "Transcription ran but the words came out wrong. Try a larger "
            "model: FASTER_WHISPER_MODEL=small",
        )
    )
    return results


# --- runner ------------------------------------------------------------------


async def run_diagnostics(settings: Settings | None = None, *, deep: bool = False) -> Report:
    settings = settings or get_settings()
    report = Report()

    report.results.append(check_python())
    report.results.append(check_binary(settings.ffmpeg_binary, "ffmpeg (audio)"))
    report.results.append(check_binary(settings.ffprobe_binary, "ffprobe (audio)"))
    report.results.append(check_work_dir(settings))
    report.results.append(await check_database(settings))
    report.results.append(check_jwt_secret(settings))
    report.results.append(check_no_paid_api(settings))
    report.results.extend(await check_transcription(settings, deep=deep))

    return report


def render(report: Report) -> str:
    """Format the report for a terminal, for a non-technical reader."""
    width = max(len(r.name) for r in report.results) + 2
    lines = ["", "Content Research Hub — system check", "=" * 52, ""]

    for result in report.results:
        mark = "OK  " if result.ok else ("WARN" if result.warning_only else "FAIL")
        lines.append(f"  [{mark}] {result.name:<{width}} {result.detail}")

    lines.append("")

    problems = report.failures + report.warnings
    if problems:
        lines.append("What to do:")
        for result in problems:
            if result.fix:
                lines.append(f"  · {result.name}: {result.fix}")
        lines.append("")

    if report.ok and not report.warnings:
        lines.append("Everything checks out. You are ready to add videos.")
    elif report.ok:
        lines.append("Usable, but see the warnings above before real use.")
    else:
        lines.append("Not ready yet — fix the FAIL items above, then run this again.")

    lines.append("")
    return "\n".join(lines)


def main(deep: bool = False) -> int:  # pragma: no cover - thin CLI wrapper
    from app.core.logging import configure_logging
    from app.db.session import dispose_db

    configure_logging("WARNING")
    report = asyncio.run(run_diagnostics(deep=deep))
    print(render(report))
    asyncio.run(dispose_db())
    return 0 if report.ok else 1
