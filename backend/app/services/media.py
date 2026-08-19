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
            "retries": 0,
            "fragment_retries": 3,
            "progress_hooks": [hook],
            "nopart": True,
        }

        from app.services.proxy import get_random_proxy
        proxy = get_random_proxy()
        if proxy:
            options["proxy"] = proxy
        return options

    def _download_sync(self, url: str, destination: Path, hook: Callable[[dict], None]) -> Path:
        try:
            import yt_dlp
        except ImportError as exc:  # pragma: no cover
            raise DownloadError("yt-dlp is not installed on the server.") from exc

        import tempfile
        import os
        
        cookie_path = None
        last_exc = None
        path = None
        
        try:
            options = self._ydl_options(destination, hook)
            if self.settings.youtube_cookies_text:
                fd, cookie_path = tempfile.mkstemp(suffix=".txt", text=True)
                with os.fdopen(fd, "w") as f:
                    f.write(self.settings.youtube_cookies_text)
                options["cookiefile"] = cookie_path

            for attempt in range(5):
                try:
                    with yt_dlp.YoutubeDL(options) as ydl:
                        info = ydl.extract_info(url, download=True)
                        if info is None:
                            raise DownloadError("Download produced no file.")
                        path = Path(ydl.prepare_filename(info))
                    break  # Success!
                except DownloadError:
                    raise
                except Exception as exc:
                    last_exc = exc
                    message = str(exc).lower()
                    # If we get a bot check or 403 Forbidden, the proxy IP is blocked. 
                    # Since we use a rotating proxy, retrying grabs a fresh IP.
                    if ("bot" in message or "sign in" in message or "403" in message or "proxy authentication required" in message):
                        if attempt < 4:
                            logger.info(f"Download proxy IP blocked or 403 Forbidden. Automatically rotating IP (attempt {attempt + 1}/5)...")
                            options = self._ydl_options(destination, hook)
                            if cookie_path:
                                options["cookiefile"] = cookie_path
                            continue
                        else:
                            pass # Let it fall out of the loop and trigger the fallback
                    elif "private" in message or "unavailable" in message or "removed" in message:
                        raise VideoUnavailableError(
                            "This video is unavailable — it may be private, deleted, or region-locked.",
                            details={"provider_message": str(exc)},
                        ) from exc
                    else:
                        raise DownloadError(f"Download failed: {str(exc)}") from exc

            if not path:
                if last_exc:
                    message = str(last_exc).lower()
                    if "bot" in message or "sign in" in message or "403" in message or "proxy authentication required" in message:
                        logger.warning("All proxy attempts were blocked by YouTube. Falling back to direct connection (NO PROXY)...")
                        try:
                            fallback_opts = self._ydl_options(destination, hook)
                            if "proxy" in fallback_opts:
                                del fallback_opts["proxy"]
                            if cookie_path:
                                fallback_opts["cookiefile"] = cookie_path
                            with yt_dlp.YoutubeDL(fallback_opts) as ydl:
                                info = ydl.extract_info(url, download=True)
                                if info is None:
                                    raise DownloadError("Fallback download produced no file.")
                                path = Path(ydl.prepare_filename(info))
                        except Exception as fallback_exc:
                            raise DownloadError(f"Download failed even without proxy: {str(fallback_exc)}") from fallback_exc
                    else:
                        raise DownloadError(f"Download failed after retries: {str(last_exc)}")
                else:
                    raise DownloadError("Download completed but no media file was written.")

            if not path or not path.exists():
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
        finally:
            if cookie_path and os.path.exists(cookie_path):
                try:
                    os.remove(cookie_path)
                except OSError:
                    pass

    async def download_video(
        self, url: str, destination: Path, on_progress: ProgressCallback | None = None
    ) -> Path:
        destination.mkdir(parents=True, exist_ok=True)
        loop = asyncio.get_running_loop()

        # Route YouTube URLs to Apify if a token is configured.
        if ("youtube.com" in url or "youtu.be" in url) and self.settings.apify_api_token:
            logger.info("YouTube URL detected and Apify Token present. Using Apify Downloader.")
            return await self._download_youtube_apify(url, destination)

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

    async def _download_youtube_apify(self, url: str, destination: Path) -> Path:
        import httpx
        
        # Use the synchronous wait endpoint for the epctex YouTube Downloader actor
        api_url = f"https://api.apify.com/v2/acts/epctex~youtube-video-downloader/run-sync-get-dataset-items"
        params = {"token": self.settings.apify_api_token}
        
        # Payload according to the actor's schema
        payload = {
            "startUrls": [url],
            "quality": "720p"
        }

        logger.info(f"Calling Apify to run epctex/youtube-video-downloader for: {url}")
        # Note: run-sync endpoint waits for the actor to finish. Actor runs can take a minute or two.
        async with httpx.AsyncClient(timeout=300) as client:
            response = await client.post(api_url, params=params, json=payload)
            
            if response.status_code != 200 and response.status_code != 201:
                logger.error(f"Apify failed: {response.status_code} {response.text}")
                raise DownloadError(f"Apify YouTube Downloader failed (HTTP {response.status_code}). Ensure your token is valid.")
            
            data = response.json()
            
        if not data or not isinstance(data, list) or len(data) == 0:
            logger.error(f"Apify returned empty or invalid dataset: {data}")
            raise DownloadError("Apify returned success, but no dataset items were found.")
            
        # Extract the storage URL from the first item
        item = data[0]
        storage_url = item.get("storageUrl")
        
        if not storage_url:
            logger.error(f"Apify returned dataset without storageUrl: {item}")
            raise DownloadError("Apify ran successfully, but could not extract a download URL for this video.")

        logger.info(f"Apify finished. Downloading MP4 directly from storage: {storage_url[:80]}...")

        file_path = destination / "source.mp4"
        
        async with httpx.AsyncClient(timeout=300) as client:
            async with client.stream("GET", storage_url) as stream_resp:
                if stream_resp.status_code != 200:
                    raise DownloadError(f"Failed to download media from Apify storage (HTTP {stream_resp.status_code})")
                async with await anyio.open_file(file_path, "wb") as f:
                    async for chunk in stream_resp.aiter_bytes():
                        await f.write(chunk)

        logger.info(f"Downloaded {url} -> {file_path.name} ({file_path.stat().st_size} bytes)")
        return file_path

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
