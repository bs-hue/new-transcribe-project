"""URL validation — step 1 and 2 of the workflow."""

from __future__ import annotations

import pytest

from app.core.errors import InvalidURLError, UnsupportedURLError
from app.platforms import parse_url, supported_platforms


@pytest.mark.parametrize(
    ("url", "video_id"),
    [
        ("https://www.youtube.com/watch?v=dQw4w9WgXcQ", "dQw4w9WgXcQ"),
        ("https://youtube.com/watch?v=dQw4w9WgXcQ&t=42s", "dQw4w9WgXcQ"),
        ("https://www.youtube.com/watch?app=desktop&v=dQw4w9WgXcQ", "dQw4w9WgXcQ"),
        ("https://youtu.be/dQw4w9WgXcQ", "dQw4w9WgXcQ"),
        ("https://youtu.be/dQw4w9WgXcQ?si=abcdef", "dQw4w9WgXcQ"),
        ("https://www.youtube.com/shorts/dQw4w9WgXcQ", "dQw4w9WgXcQ"),
        ("https://www.youtube.com/embed/dQw4w9WgXcQ", "dQw4w9WgXcQ"),
        ("https://www.youtube.com/live/dQw4w9WgXcQ", "dQw4w9WgXcQ"),
        ("youtube.com/watch?v=dQw4w9WgXcQ", "dQw4w9WgXcQ"),
    ],
)
def test_youtube_urls_are_recognised(url: str, video_id: str) -> None:
    parsed = parse_url(url)
    assert parsed.platform == "youtube"
    assert parsed.video_id == video_id
    assert parsed.canonical_url == f"https://www.youtube.com/watch?v={video_id}"


@pytest.mark.parametrize(
    ("url", "video_id"),
    [
        ("https://www.instagram.com/reel/CxYz123abc/", "CxYz123abc"),
        ("https://instagram.com/reels/CxYz123abc", "CxYz123abc"),
        ("https://www.instagram.com/p/CxYz123abc/", "CxYz123abc"),
        ("https://www.instagram.com/tv/CxYz123abc/", "CxYz123abc"),
        ("https://www.instagram.com/somecreator/reel/CxYz123abc/", "CxYz123abc"),
        ("https://www.instagram.com/reel/CxYz123abc/?igsh=xyz", "CxYz123abc"),
    ],
)
def test_instagram_urls_are_recognised(url: str, video_id: str) -> None:
    parsed = parse_url(url)
    assert parsed.platform == "instagram"
    assert parsed.video_id == video_id


@pytest.mark.parametrize(
    ("url", "video_id"),
    [
        ("https://www.facebook.com/ads/library/?id=4437908863142926", "4437908863142926"),
        ("https://www.facebook.com/ads/archive/render_ad/?id=4437908863142926", "4437908863142926"),
        ("https://facebook.com/ads/library/?active_status=all&country=IN&id=4437908863142926", "4437908863142926"),
        ("https://www.facebook.com/watch/?v=1234567890", "1234567890"),
        ("https://www.facebook.com/reel/1234567890", "1234567890"),
        ("https://fb.watch/abcd1234/", "abcd1234"),
    ],
)
def test_facebook_urls_are_recognised(url: str, video_id: str) -> None:
    parsed = parse_url(url)
    assert parsed.platform == "facebook"
    assert parsed.video_id == video_id


def test_canonical_url_deduplicates_url_variants() -> None:
    """Two spellings of the same video must resolve to one identity."""
    a = parse_url("https://youtu.be/dQw4w9WgXcQ")
    b = parse_url("https://www.youtube.com/watch?v=dQw4w9WgXcQ&list=PL123")
    assert (a.platform, a.video_id) == (b.platform, b.video_id)


def test_original_url_is_preserved() -> None:
    parsed = parse_url("  https://youtu.be/dQw4w9WgXcQ  ")
    assert parsed.original_url == "https://youtu.be/dQw4w9WgXcQ"


@pytest.mark.parametrize(
    "url",
    [
        "https://vimeo.com/123456",
        "https://www.tiktok.com/@user/video/123",
        "https://example.com/video.mp4",
    ],
)
def test_unsupported_platforms_are_rejected(url: str) -> None:
    with pytest.raises(UnsupportedURLError):
        parse_url(url)


def test_channel_link_gets_a_specific_message() -> None:
    with pytest.raises(UnsupportedURLError) as exc:
        parse_url("https://www.youtube.com/@somechannel")
    assert "not a single video" in exc.value.message


@pytest.mark.parametrize("url", ["", "   ", "not a url at all"])
def test_malformed_input_is_rejected(url: str) -> None:
    with pytest.raises((InvalidURLError, UnsupportedURLError)):
        parse_url(url)


@pytest.mark.parametrize(
    "url",
    ["file:///etc/passwd", "ftp://example.com/x", "gopher://evil.internal/"],
)
def test_non_http_schemes_are_rejected(url: str) -> None:
    """First line of SSRF defence: nothing but http(s) gets past validation."""
    with pytest.raises(InvalidURLError):
        parse_url(url)


def test_supported_platforms_are_advertised() -> None:
    names = {platform["name"] for platform in supported_platforms()}
    assert names == {"youtube", "instagram", "facebook"}
