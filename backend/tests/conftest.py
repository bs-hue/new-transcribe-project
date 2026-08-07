"""Test fixtures.

Everything here runs without network access, ffmpeg, or API keys: the media
backend is faked and the transcription provider is the stub. That is deliberate —
a test suite that needs credentials is a test suite nobody runs.
"""

from __future__ import annotations

import os
import shutil
import tempfile
from collections.abc import AsyncIterator
from pathlib import Path

import pytest

# Configure before anything imports settings.
_TMP = Path(tempfile.mkdtemp(prefix="research-hub-tests-"))
os.environ.update(
    {
        "DATABASE_URL": f"sqlite+aiosqlite:///{_TMP / 'test.db'}",
        "TRANSCRIPTION_PROVIDER": "stub",
        "WORKER_ENABLED": "false",
        "WORK_DIR": str(_TMP / "work"),
        "MAX_URLS_PER_REQUEST": "10",
        "JWT_SECRET": "test-secret-not-used-outside-the-test-suite",
        "ENVIRONMENT": "development",
        "BOOTSTRAP_ADMIN_EMAIL": "",
        "BOOTSTRAP_ADMIN_PASSWORD": "",
    }
)

from httpx import ASGITransport, AsyncClient  # noqa: E402

from app.config import get_settings  # noqa: E402
from app.db import session as db_session  # noqa: E402
from app.db.models import Base  # noqa: E402
from app.services import media as media_module  # noqa: E402
from app.services import search as search_module  # noqa: E402
from app.services.transcription import reset_provider_cache  # noqa: E402


class FakeMediaBackend:
    """Writes plausible files instead of touching the network or ffmpeg."""

    def __init__(self) -> None:
        self.audio_size = 1024
        self.downloaded: list[str] = []

    async def download_video(self, url, destination, on_progress=None):  # noqa: ANN001
        self.downloaded.append(url)
        destination.mkdir(parents=True, exist_ok=True)
        path = destination / "source.mp4"
        path.write_bytes(b"\x00" * 2048)
        if on_progress:
            await on_progress(1.0)
        return path

    async def extract_audio(self, video_path, destination):  # noqa: ANN001
        destination.mkdir(parents=True, exist_ok=True)
        path = destination / "audio.wav"
        path.write_bytes(b"\x00" * self.audio_size)
        return path

    async def split_audio(self, audio_path, chunk_seconds):  # noqa: ANN001
        chunk_dir = audio_path.parent / "chunks"
        chunk_dir.mkdir(parents=True, exist_ok=True)
        chunks = []
        for index in range(2):
            path = chunk_dir / f"chunk_{index:04d}.wav"
            path.write_bytes(b"\x00" * 512)
            chunks.append((path, float(index * chunk_seconds)))
        return chunks


@pytest.fixture(scope="session", autouse=True)
def _cleanup_tmp() -> AsyncIterator[None]:
    yield
    shutil.rmtree(_TMP, ignore_errors=True)


@pytest.fixture
def settings():
    get_settings.cache_clear()
    reset_provider_cache()
    return get_settings()


@pytest.fixture
async def database(settings) -> AsyncIterator[None]:
    """A fresh schema per test."""
    await db_session.dispose_db()
    search_module.reset_search_backend()

    engine = db_session.get_engine(settings)
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.drop_all)
        await conn.exec_driver_sql("DROP TABLE IF EXISTS transcript_fts")
    await db_session.init_db(settings)

    yield

    await db_session.dispose_db()


@pytest.fixture
async def session(database) -> AsyncIterator:
    async with db_session.get_session_factory()() as db:
        yield db


@pytest.fixture
def fake_media() -> AsyncIterator[FakeMediaBackend]:
    backend = FakeMediaBackend()
    media_module.set_media_backend(backend)
    yield backend
    media_module.set_media_backend(None)


@pytest.fixture
async def client_factory(database, fake_media) -> AsyncIterator:
    """Builds independent HTTP clients against one app instance.

    A factory rather than a plain fixture because signed-in and anonymous
    clients must not share a headers dict — otherwise signing one in silently
    signs the other in too, and a test that means to check authorisation
    quietly checks nothing.

    The `database` fixture already built the schema; running lifespan again
    would also start workers, which these tests drive explicitly instead.
    """
    from app.main import create_app

    app = create_app()
    opened: list[AsyncClient] = []

    def build() -> AsyncClient:
        http = AsyncClient(transport=ASGITransport(app=app), base_url="http://test")
        opened.append(http)
        return http

    yield build

    for http in opened:
        await http.aclose()


@pytest.fixture
async def anonymous_client(client_factory) -> AsyncClient:
    """A client with no credentials, for checking that auth is enforced."""
    return client_factory()


async def _make_user(email: str, password: str, *, admin: bool) -> None:
    from app.db.models import UserRole
    from app.db.session import session_scope
    from app.services.users import create_user

    async with session_scope() as db:
        await create_user(
            db,
            email=email,
            password=password,
            role=UserRole.ADMIN.value if admin else UserRole.MEMBER.value,
        )


@pytest.fixture
async def member_credentials(database) -> tuple[str, str]:
    await _make_user("writer@agency.test", "member-password", admin=False)
    return "writer@agency.test", "member-password"


@pytest.fixture
async def admin_credentials(database) -> tuple[str, str]:
    await _make_user("admin@agency.test", "admin-password", admin=True)
    return "admin@agency.test", "admin-password"


async def _sign_in(http: AsyncClient, email: str, password: str) -> AsyncClient:
    response = await http.post("/api/auth/login", json={"email": email, "password": password})
    assert response.status_code == 200, response.text
    http.headers["Authorization"] = f"Bearer {response.json()['access_token']}"
    return http


@pytest.fixture
async def client(client_factory, member_credentials) -> AsyncClient:
    """A client signed in as an ordinary team member. Most tests want this."""
    return await _sign_in(client_factory(), *member_credentials)


@pytest.fixture
async def admin_client(client_factory, admin_credentials) -> AsyncClient:
    """A separate client signed in as an admin."""
    return await _sign_in(client_factory(), *admin_credentials)
