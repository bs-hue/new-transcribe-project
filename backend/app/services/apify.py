"""Apify integration for transcript fetching."""

import logging
from typing import Any

import httpx

from app.core.errors import AppError, TranscriptionError
from app.services.transcription import TranscriptionResult, TranscriptSegmentData

logger = logging.getLogger(__name__)

class ApifyError(AppError):
    """An error interacting with Apify."""
    pass


async def fetch_youtube_transcript_apify(url: str, token: str, language: str | None = None) -> TranscriptionResult:
    """Fetch a transcript directly from YouTube using the starvibe Apify actor."""
    api_url = "https://api.apify.com/v2/acts/starvibe~youtube-video-transcript/run-sync-get-dataset-items"
    params = {"token": token}
    payload = {
        "youtube_url": url,
    }
    if language:
        payload["language"] = language

    logger.info("Calling Apify (starvibe/youtube-video-transcript) for %s", url)
    
    async with httpx.AsyncClient(timeout=300) as client:
        try:
            response = await client.post(api_url, params=params, json=payload)
            if response.status_code not in (200, 201):
                logger.error("Apify actor failed: %d %s", response.status_code, response.text)
                raise ApifyError(f"Apify transcript extraction failed (HTTP {response.status_code}). Check your token or video URL.")
            data = response.json()
        except httpx.RequestError as exc:
            raise ApifyError(f"Connection to Apify failed: {exc}") from exc

    if not data or not isinstance(data, list) or len(data) == 0:
        raise ApifyError("Apify returned success but no data was found.")

    item = data[0]
    
    if item.get("status") == "error":
        msg = item.get("message", "Unknown error fetching transcript from YouTube.")
        raise TranscriptionError(f"Could not extract transcript: {msg}")

    transcript_list = item.get("transcript", [])
    if not transcript_list:
        raise TranscriptionError("No transcript or closed captions available for this video.")

    segments: list[TranscriptSegmentData] = []
    full_text_parts: list[str] = []

    for idx, seg in enumerate(transcript_list):
        text = seg.get("text", "").strip()
        if not text:
            continue
            
        full_text_parts.append(text)
        segments.append(
            TranscriptSegmentData(
                index=idx,
                start=float(seg.get("start", 0.0)),
                end=float(seg.get("end", 0.0)),
                text=text,
                speaker=None,
            )
        )

    return TranscriptionResult(
        text=" ".join(full_text_parts),
        language=item.get("language", "en"),
        segments=segments,
        duration_seconds=float(item["duration_seconds"]) if item.get("duration_seconds") else None,
        provider="apify (starvibe)",
        model="youtube-captions",
    )


async def get_youtube_audio_url_thenetaji(url: str, token: str) -> str:
    """Fetch a direct audio download URL using thenetaji/youtube-video-downloader-advanced."""
    api_url = "https://api.apify.com/v2/acts/thenetaji~youtube-video-downloader-advanced/run-sync-get-dataset-items"
    params = {"token": token}
    payload = {
        "urls": [{"url": url}]
    }

    logger.info("Calling Apify (thenetaji/youtube-video-downloader-advanced) for %s", url)
    
    async with httpx.AsyncClient(timeout=300) as client:
        try:
            response = await client.post(api_url, params=params, json=payload)
            if response.status_code not in (200, 201):
                raise ApifyError(f"Apify thenetaji actor failed (HTTP {response.status_code})")
            data = response.json()
        except httpx.RequestError as exc:
            raise ApifyError(f"Connection to Apify failed: {exc}") from exc

    if not data or not isinstance(data, list) or len(data) == 0:
        raise ApifyError("Apify returned success but no data was found.")

    item = data[0]
    if item.get("status") != "ok":
        raise ApifyError("Actor did not return ok status.")
        
    video_info = item.get("videoInfo", {})
    adaptive_formats = video_info.get("adaptiveFormats", [])
    
    # Prioritize audio-only streams
    for fmt in adaptive_formats:
        mime = fmt.get("mimeType", "")
        if mime.startswith("audio/"):
            stream_url = fmt.get("url")
            if stream_url:
                return stream_url
                
    raise ApifyError("No audio streams found in the thenetaji response.")


async def get_youtube_audio_url_crawlerbros(url: str, token: str) -> str:
    """Fetch a direct audio download URL using crawlerbros/youtube-video-downloader."""
    api_url = "https://api.apify.com/v2/acts/crawlerbros~youtube-video-downloader/run-sync-get-dataset-items"
    params = {"token": token}
    payload = {
        "videoUrls": [url],
        "videoQuality": "audio_only",
        "downloadSubtitles": False,
        "extractMetadataOnly": False,
        "proxyCountry": "IN"
    }

    logger.info("Calling Apify (crawlerbros/youtube-video-downloader) for %s", url)
    
    async with httpx.AsyncClient(timeout=300) as client:
        try:
            response = await client.post(api_url, params=params, json=payload)
            if response.status_code not in (200, 201):
                raise ApifyError(f"Apify crawlerbros actor failed (HTTP {response.status_code})")
            data = response.json()
        except httpx.RequestError as exc:
            raise ApifyError(f"Connection to Apify failed: {exc}") from exc

    if not data or not isinstance(data, list) or len(data) == 0:
        raise ApifyError("Apify crawlerbros returned no data.")

    item = data[0]
    # Crawlerbros typically returns the downloadUrl directly
    audio_url = item.get("downloadUrl") or item.get("audioUrl") or item.get("url")
    if audio_url:
        return audio_url

    raise ApifyError("No audio URL found in the crawlerbros response.")

