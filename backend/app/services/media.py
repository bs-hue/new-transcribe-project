"""Download and audio extraction.

Two responsibilities, both shelling out to well-established tools:

* ``download_video`` — yt-dlp, with progress reported back to the caller.
* ``extract_audio`` — ffmpeg, producing 16 kHz mono WAV, which is what every
  speech model actually wants and is far smaller than the source video.

Both are exposed through the ``MediaBackend`` protocol so the pipeline can be
tested end-to-end without network access or ffmpeg installed.
"""

from __future__ import annotations

import asyncio
import logging
import shutil
import uuid
from collections.abc import Awaitable, Callable
from contextlib import suppress
from pathlib import Path
from typing import Any, Protocol

import anyio

from app.config import Settings, get_settings
from app.core.errors import AudioExtractionError, DownloadError, VideoUnavailableError

logger = logging.getLogger(__name__)

ProgressCallback = Callable[[float], Awaitable[None]]

# Target audio format. 16 kHz mono PCM is the de-facto input for Whisper-family
# models; anything higher is discarded by the model anyway.
AUDIO_SAMPLE_RATE = 16_000
AUDIO_CHANNELS = 1


class MediaBackend(Protocol):
    """What the pipeline needs from the outside world."""

    async def download_video(
        self, url: str, destination: Path, on_progress: ProgressCallback | None = None
    ) -> Path: ...

    async def extract_audio(self, video_path: Path, destination: Path) -> Path: ...

    async def split_audio(self, audio_path: Path, chunk_seconds: int) -> list[tuple[Path, float]]:
        """Split into chunks, returning ``(path, start_offset_seconds)`` pairs."""
        ...


class WorkDirectory:
    """A scratch directory for one job, cleaned up unless KEEP_MEDIA is set."""

    def __init__(self, root: Path, job_id: str, *, keep: bool = False) -> None:
        self.path = root / job_id
        self.path.mkdir(parents=True, exist_ok=True)
        self._keep = keep

    def __enter__(self) -> WorkDirectory:
        return self

    def __exit__(self, *_exc: object) -> None:
        self.cleanup()

    def cleanup(self) -> None:
        if self._keep:
            logger.info("KEEP_MEDIA is on; leaving %s in place", self.path)
            return
        with suppress(OSError):
            shutil.rmtree(self.path, ignore_errors=True)


class RealMediaBackend:
    """yt-dlp + ffmpeg."""

    def __init__(self, settings: Settings | None = None) -> None:
        self.settings = settings or get_settings()

    # --- download ---------------------------------------------------------

    def _ydl_options(self, destination: Path, hook: Callable[[dict], None]) -> dict[str, Any]:
        options: dict[str, Any] = {
            "quiet": True,
            "no_warnings": True,
            "noplaylist": True,
            "outtmpl": str(destination / "source.%(ext)s"),
            # Prefer a modest-resolution muxed file: we only ever want the audio,
            # so downloading 4K video would waste bandwidth and disk for nothing.
            "format": "bestaudio/best[height<=720]/best",
            "socket_timeout": 30,
            "retries": 3,
            "fragment_retries": 3,
            "progress_hooks": [hook],
            "nopart": True,
            "source_address": "0.0.0.0",
            "extractor_args": {"youtube": ["client=android,ios"]},
        }
        if self.settings.cookies_file:
            options["cookiefile"] = str(self.settings.cookies_file)
        if self.settings.youtube_proxy:
            options["proxy"] = self.settings.youtube_proxy
        return options

    def _download_sync(self, url: str, destination: Path, hook: Callable[[dict], None]) -> Path:
        try:
            import yt_dlp
        except ImportError as exc:  # pragma: no cover
            raise DownloadError("yt-dlp is not installed on the server.") from exc

        try:
            with yt_dlp.YoutubeDL(self._ydl_options(destination, hook)) as ydl:
                info = ydl.extract_info(url, download=True)
                if info is None:
                    raise DownloadError("Download produced no file.")
                path = Path(ydl.prepare_filename(info))
        except DownloadError:
            raise
        except Exception as exc:
            message = str(exc)
            lowered = message.lower()
            if "private" in lowered or "unavailable" in lowered or "removed" in lowered:
                raise VideoUnavailableError(
                    "This video is unavailable — it may be private, deleted, or region-locked.",
                    details={"provider_message": message},
                ) from exc
            raise DownloadError(f"Download failed: {message}") from exc

        if not path.exists():
            # yt-dlp remuxes and the predicted extension can be wrong; take
            # whatever landed in our (job-private) directory.
            candidates = sorted(
                (p for p in destination.glob("source.*") if p.is_file()),
                key=lambda p: p.stat().st_size,
                reverse=True,
            )
            if not candidates:
                raise DownloadError("Download completed but no media file was written.")
            path = candidates[0]

        return path

    async def download_video(
        self, url: str, destination: Path, on_progress: ProgressCallback | None = None
    ) -> Path:
        destination.mkdir(parents=True, exist_ok=True)
        loop = asyncio.get_running_loop()

        def hook(status: dict) -> None:
            if on_progress is None or status.get("status") != "downloading":
                return
            total = status.get("total_bytes") or status.get("total_bytes_estimate")
            downloaded = status.get("downloaded_bytes") or 0
            if not total:
                return
            fraction = min(1.0, downloaded / total)
            # The hook runs on the worker thread; hop back to the loop to await.
            asyncio.run_coroutine_threadsafe(on_progress(fraction), loop)

        path = await anyio.to_thread.run_sync(self._download_sync, url, destination, hook)
        logger.info("Downloaded %s -> %s (%d bytes)", url, path.name, path.stat().st_size)
        return path

    # --- audio ------------------------------------------------------------

    async def _run(self, *args: str, error: str) -> bytes:
        """Run a binary with an argument list — never a shell string."""
        import subprocess

        def _sync_run() -> bytes:
            try:
                result = subprocess.run(
                    args,
                    stdout=subprocess.PIPE,
                    stderr=subprocess.PIPE,
                )
            except FileNotFoundError as exc:
                raise AudioExtractionError(
                    f"{args[0]} was not found on PATH. Install ffmpeg to process audio."
                ) from exc

            if result.returncode != 0:
                detail = result.stderr.decode("utf-8", "replace").strip().splitlines()
                raise AudioExtractionError(
                    f"{error}: {detail[-1] if detail else f'exit code {result.returncode}'}"
                )
            return result.stdout

        return await anyio.to_thread.run_sync(_sync_run)

    async def extract_audio(self, video_path: Path, destination: Path) -> Path:
        destination.mkdir(parents=True, exist_ok=True)
        audio_path = destination / "audio.wav"
        await self._run(
            self.settings.ffmpeg_binary,
            "-nostdin",
            "-y",
            "-i", str(video_path),
            "-vn",
            "-ac", str(AUDIO_CHANNELS),
            "-ar", str(AUDIO_SAMPLE_RATE),
            "-acodec", "pcm_s16le",
            str(audio_path),
            error="Audio extraction failed",
        )
        if not audio_path.exists() or audio_path.stat().st_size == 0:
            raise AudioExtractionError("Audio extraction produced an empty file.")
        return audio_path

    async def split_audio(self, audio_path: Path, chunk_seconds: int) -> list[tuple[Path, float]]:
        """Segment audio into fixed-length parts for providers with size caps.

        Returns ``(path, start_offset)`` so the caller can shift each chunk's
        timestamps back onto the original timeline.
        """
        chunk_dir = audio_path.parent / "chunks"
        chunk_dir.mkdir(parents=True, exist_ok=True)
        pattern = str(chunk_dir / "chunk_%04d.wav")

        await self._run(
            self.settings.ffmpeg_binary,
            "-nostdin",
            "-y",
            "-i", str(audio_path),
            "-f", "segment",
            "-segment_time", str(chunk_seconds),
            "-c", "copy",
            pattern,
            error="Audio segmentation failed",
        )

        chunks = sorted(chunk_dir.glob("chunk_*.wav"))
        if not chunks:
            raise AudioExtractionError("Audio segmentation produced no chunks.")
        return [(path, float(index * chunk_seconds)) for index, path in enumerate(chunks)]


def new_work_directory(
    job_id: str | None = None, settings: Settings | None = None
) -> WorkDirectory:
    settings = settings or get_settings()
    return WorkDirectory(
        settings.resolved_work_dir(),
        job_id or uuid.uuid4().hex,
        keep=settings.keep_media,
    )


_backend: MediaBackend | None = None


def get_media_backend(settings: Settings | None = None) -> MediaBackend:
    global _backend
    if _backend is None:
        _backend = RealMediaBackend(settings)
    return _backend


def set_media_backend(backend: MediaBackend | None) -> None:
    """Swap the backend. Used by tests to run the pipeline without network."""
    global _backend
    _backend = backend
