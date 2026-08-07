"""Dashboard summary and runtime settings — the backend behind the new screens."""

from __future__ import annotations

import pytest

from app.core.errors import AppError
from app.services import pipeline as pipeline_module
from app.services.ingest import submit_urls
from app.services.metadata import VideoMetadata
from app.services.pipeline import Pipeline
from app.services.settings_store import (
    current_values,
    effective_settings,
    update_settings,
)

URL = "https://www.youtube.com/watch?v=dQw4w9WgXcQ"
SECOND = "https://www.instagram.com/reel/CxYz123abc/"


@pytest.fixture
def patched_metadata(monkeypatch):
    async def fake_fetch(parsed, settings=None):  # noqa: ANN001
        return VideoMetadata(
            platform=parsed.platform,
            platform_video_id=parsed.video_id,
            canonical_url=parsed.canonical_url,
            source_url=parsed.original_url,
            title=f"Video {parsed.video_id}",
            author="Creator Name",
            duration_seconds=60.0,
            estimated_size_bytes=1024 * 1024,
        )

    monkeypatch.setattr(pipeline_module, "fetch_metadata", fake_fetch)


# --- dashboard ---------------------------------------------------------------


async def test_dashboard_is_empty_on_a_fresh_install(client) -> None:
    payload = (await client.get("/api/dashboard")).json()
    assert payload["in_progress"] == 0
    assert payload["needs_attention"] == 0
    assert payload["total_research"] == 0
    assert payload["active_jobs"] == []
    assert payload["recent_transcripts"] == []


async def test_dashboard_counts_queued_work(client, session) -> None:
    await submit_urls(session, [URL, SECOND])

    payload = (await client.get("/api/dashboard")).json()
    assert payload["in_progress"] == 2
    assert len(payload["active_jobs"]) == 2
    # The strip must carry enough to render a row without a second request.
    assert payload["active_jobs"][0]["video"] is not None


async def test_dashboard_counts_completed_work_and_lists_it(
    client, session, settings, fake_media, patched_metadata
) -> None:
    result = await submit_urls(session, [URL])
    await Pipeline(settings).run(result.outcomes[0].job_id)
    await session.commit()

    payload = (await client.get("/api/dashboard")).json()
    assert payload["in_progress"] == 0
    assert payload["finished_today"] == 1
    assert payload["total_research"] == 1
    assert len(payload["recent_transcripts"]) == 1
    assert payload["recent_transcripts"][0]["video"]["title"] == "Video dQw4w9WgXcQ"


async def test_transcribing_the_same_video_twice_still_counts_as_one(
    client, session, settings, fake_media, patched_metadata
) -> None:
    """"Total research" is clickable and lands on History, which lists videos.
    A second transcript of the same video must not make the two disagree, nor
    show the video twice under "Recent research"."""
    for _ in range(2):
        result = await submit_urls(session, [URL])
        await Pipeline(settings).run(result.outcomes[0].job_id)
        await session.commit()

    payload = (await client.get("/api/dashboard")).json()
    assert payload["finished_today"] == 2  # two jobs really did run
    assert payload["total_research"] == 1  # but it is one video
    assert len(payload["recent_transcripts"]) == 1

    listed = (await client.get("/api/videos", params={"has_transcript": True})).json()
    assert listed["total"] == payload["total_research"]


async def test_dashboard_surfaces_failures(
    client, session, settings, fake_media, monkeypatch
) -> None:
    from app.core.errors import VideoUnavailableError

    async def fails(parsed, settings=None):  # noqa: ANN001
        raise VideoUnavailableError("This video is private.")

    monkeypatch.setattr(pipeline_module, "fetch_metadata", fails)

    result = await submit_urls(session, [URL])
    with pytest.raises(VideoUnavailableError):
        await Pipeline(settings).run(result.outcomes[0].job_id)
    await session.commit()

    payload = (await client.get("/api/dashboard")).json()
    assert payload["needs_attention"] == 1


# --- who submitted -----------------------------------------------------------


async def test_a_job_records_who_submitted_it(client, member_credentials) -> None:
    submission = (await client.post("/api/videos", json={"urls": [URL]})).json()
    job = (await client.get(f"/api/jobs/{submission['results'][0]['job_id']}")).json()

    assert job["submitted_by"] is not None
    assert job["submitted_by_name"] == member_credentials[0]


async def test_removing_a_user_keeps_their_jobs(
    client, admin_client, member_credentials
) -> None:
    """Deleting a colleague must not delete the research they collected."""
    submission = (await client.post("/api/videos", json={"urls": [URL]})).json()
    job_id = submission["results"][0]["job_id"]

    users = (await admin_client.get("/api/auth/users")).json()
    member = next(u for u in users if u["email"] == member_credentials[0])
    assert (await admin_client.delete(f"/api/auth/users/{member['id']}")).status_code == 204

    job = (await admin_client.get(f"/api/jobs/{job_id}")).json()
    assert job["id"] == job_id           # the job survives
    assert job["submitted_by"] is None   # the link is cleared, not cascaded


# --- settings ----------------------------------------------------------------


async def test_settings_report_the_environment_defaults(client) -> None:
    payload = (await client.get("/api/settings")).json()
    assert payload["values"]["max_urls_per_request"] == 10  # set by the test env
    assert payload["transcription_provider"] == "stub"
    keys = {d["key"] for d in payload["definitions"]}
    assert "faster_whisper_model" in keys
    # Every definition must carry guidance, or the screen cannot explain itself.
    assert all(d["help"] and d["applies_to"] for d in payload["definitions"])


async def test_every_number_says_what_it_counts(client) -> None:
    """A raw 2147483648 is unreadable. Numbers carry a unit so the screen can
    print "2 GB" beside the box; text settings have no unit to carry."""
    for definition in (await client.get("/api/settings")).json()["definitions"]:
        if definition["kind"] == "int":
            assert definition["unit"] in {"seconds", "bytes", "count"}, definition["key"]
        else:
            assert definition["unit"] is None, definition["key"]


async def test_an_admin_can_change_a_limit(admin_client) -> None:
    response = await admin_client.patch(
        "/api/settings", json={"values": {"max_urls_per_request": 25}}
    )
    assert response.status_code == 200
    assert response.json()["values"]["max_urls_per_request"] == 25
    assert (await admin_client.get("/api/settings")).json()["values"][
        "max_urls_per_request"
    ] == 25


async def test_a_member_cannot_change_settings(client) -> None:
    response = await client.patch(
        "/api/settings", json={"values": {"max_urls_per_request": 25}}
    )
    assert response.status_code == 403


async def test_a_changed_limit_takes_effect_without_a_restart(
    admin_client, client
) -> None:
    """The whole point of storing these: no redeploy to change a limit."""
    urls = [f"https://youtu.be/{'a' * 10}{i}" for i in range(12)]

    # Default in the test environment is 10, so 12 is refused.
    assert (await client.post("/api/videos", json={"urls": urls})).status_code == 500

    await admin_client.patch("/api/settings", json={"values": {"max_urls_per_request": 20}})

    assert (await client.post("/api/videos", json={"urls": urls})).status_code == 202


async def test_out_of_range_values_are_refused_with_a_readable_reason(
    admin_client,
) -> None:
    response = await admin_client.patch(
        "/api/settings", json={"values": {"max_urls_per_request": 9999}}
    )
    assert response.status_code == 500
    assert "at most" in response.json()["message"]


async def test_an_unknown_model_name_is_refused(admin_client) -> None:
    response = await admin_client.patch(
        "/api/settings", json={"values": {"faster_whisper_model": "enormous"}}
    )
    assert response.status_code == 500
    assert "tiny" in response.json()["message"]


async def test_settings_outside_the_allowlist_cannot_be_written(session) -> None:
    """The signing key and database URL must not be reachable from the UI."""
    for key in ("jwt_secret", "database_url", "cors_origins"):
        with pytest.raises(AppError) as exc:
            await update_settings(session, {key: "anything"})
        assert "not a changeable setting" in exc.value.message.lower()


async def test_overrides_do_not_mutate_the_shared_settings_object(
    session, settings
) -> None:
    """A request that changes a limit must not affect a job already in flight."""
    before = settings.max_urls_per_request
    await update_settings(session, {"max_urls_per_request": 42})

    effective = await effective_settings(session, settings)
    assert effective.max_urls_per_request == 42
    assert settings.max_urls_per_request == before  # the original is untouched
    assert (await current_values(session))["max_urls_per_request"] == 42


# --- system check ------------------------------------------------------------


async def test_an_admin_can_run_the_system_check_from_the_browser(admin_client) -> None:
    payload = (await admin_client.get("/api/settings/system-check")).json()
    names = {r["name"] for r in payload["results"]}
    assert "Database" in names
    assert "Where audio is processed" in names
    assert payload["text"].startswith("\nContent Research Hub")


async def test_a_member_cannot_run_the_system_check(client) -> None:
    assert (await client.get("/api/settings/system-check")).status_code == 403


# --- transcription tuning ----------------------------------------------------


def test_cpu_is_split_between_workers_not_fought_over() -> None:
    """Two workers each grabbing every core is slower overall than each taking
    half. Bulk throughput is what matters here, not one video's finish time."""
    from app.services.transcription.faster_whisper import resolve_cpu_threads

    assert resolve_cpu_threads(0, 1) >= 1
    assert resolve_cpu_threads(0, 2) <= resolve_cpu_threads(0, 1)
    # An explicit setting always wins over the automatic split.
    assert resolve_cpu_threads(3, 8) == 3


def test_the_default_precision_is_the_fast_one() -> None:
    """faster-whisper's own default is float32 on CPU — the slowest option it
    offers. Anything explicit is passed through untouched."""
    from app.services.transcription.faster_whisper import resolve_compute_type

    assert resolve_compute_type("default", "cpu") == "int8"
    assert resolve_compute_type("default", "cuda") == "float16"
    assert resolve_compute_type("float32", "cpu") == "float32"


async def test_hindi_is_offered_by_name_not_by_code(client) -> None:
    """A dropdown listing 'hi' helps nobody choose Hindi."""
    payload = (await client.get("/api/settings")).json()
    language = [d for d in payload["definitions"] if d["key"] == "transcription_language"][0]
    assert "hi" in language["choices"]
    assert language["choice_labels"]["hi"] == "Hindi"
    assert language["choice_labels"][""] == "Detect automatically"
    # Every offered choice must be nameable, or the dropdown shows a raw code.
    assert set(language["choices"]) <= set(language["choice_labels"])


async def test_the_model_choices_say_what_they_cost(client) -> None:
    payload = (await client.get("/api/settings")).json()
    model = [d for d in payload["definitions"] if d["key"] == "faster_whisper_model"][0]
    assert set(model["choices"]) <= set(model["choice_labels"])
    assert "Hindi" in model["help"] or "Indian" in model["help"]


async def test_domain_words_can_be_declared_without_touching_a_file(
    admin_client,
) -> None:
    """An agency's jargon changes per client. Whisper guesses unknown words from
    sound, so the list has to be editable by the people who know it."""
    words = "black obsidian, tiger eye, rudraksha, Vastu"
    response = await admin_client.patch(
        "/api/settings", json={"values": {"transcription_vocabulary": words}}
    )
    assert response.status_code == 200
    assert response.json()["values"]["transcription_vocabulary"] == words


def test_repetition_is_penalised_by_default() -> None:
    """Whisper locks into "yaa yaa yaa" loops on Indic audio. Two independent
    guards: no previous-text conditioning, and a repetition penalty above 1."""
    from app.config import Settings

    assert Settings().faster_whisper_repetition_penalty > 1.0


async def test_the_settings_screen_actually_reaches_the_transcriber(
    session, settings, fake_media, patched_metadata, monkeypatch
) -> None:
    """The bug this exists to prevent: settings were read once at startup, so
    changing the spoken language or the model on the Settings screen changed
    nothing at all. Hindi videos kept coming back transcribed as if English."""
    seen: dict[str, object] = {}

    from app.services.transcription import base as base_module

    class Recorder(base_module.TranscriptionProvider):
        name = "recorder"
        max_audio_bytes = None

        def __init__(self, provider_settings) -> None:  # noqa: ANN001
            seen["model"] = provider_settings.faster_whisper_model
            seen["vocabulary"] = provider_settings.transcription_vocabulary

        async def transcribe(self, audio_path, *, language=None):  # noqa: ANN001
            seen["language"] = language
            return base_module.TranscriptionResult(
                text="ok", segments=[], language=language, provider=self.name
            )

    monkeypatch.setattr(
        "app.services.pipeline.get_transcription_provider", lambda s: Recorder(s)
    )

    await update_settings(
        session,
        {
            "transcription_language": "hi",
            "faster_whisper_model": "medium",
            "transcription_vocabulary": "black obsidian, tiger eye",
        },
    )

    result = await submit_urls(session, [URL])
    await Pipeline(settings).run(result.outcomes[0].job_id)

    assert seen["language"] == "hi"
    assert seen["model"] == "medium"
    assert seen["vocabulary"] == "black obsidian, tiger eye"


# --- language, by the name a person would type -------------------------------


def test_the_language_can_be_typed_by_name() -> None:
    """The Settings screen once had a free-text box. Someone typed "Hindi",
    which is the only sensible thing to type, and Whisper — which wants "hi" —
    treated it as no language at all and quietly went back to guessing."""
    from app.services.transcription.languages import normalise

    assert normalise("Hindi") == "hi"
    assert normalise("hindi") == "hi"
    assert normalise("hi") == "hi"
    assert normalise("Hinglish") == "hi"  # still Hindi as far as the model knows
    assert normalise("") is None
    assert normalise(None) is None


def test_an_unknown_language_is_refused_rather_than_ignored() -> None:
    from app.core.errors import AppError
    from app.services.transcription.languages import normalise

    with pytest.raises(AppError) as caught:
        normalise("Klingon")
    assert "Hindi" in str(caught.value)  # the message lists what does work


async def test_a_language_name_saved_from_the_screen_is_stored_as_a_code(
    admin_client,
) -> None:
    response = await admin_client.patch(
        "/api/settings", json={"values": {"transcription_language": "Hindi"}}
    )
    assert response.status_code == 200
    assert response.json()["values"]["transcription_language"] == "hi"


def test_a_language_name_in_the_env_file_also_works() -> None:
    from app.config import Settings

    assert Settings(transcription_language="Hindi").transcription_language == "hi"


async def test_a_language_stored_before_validation_existed_is_healed(session) -> None:
    """A real install had "Hindi" written into the database by an earlier build
    with a free-text box. Validating only on save left it there, failing every
    job. Reading normalises too, so the bad row fixes itself."""
    from app.db.models import AppSetting

    session.add(AppSetting(key="transcription_language", value="Hindi"))
    await session.commit()

    effective = await effective_settings(session)
    assert effective.transcription_language == "hi"


async def test_a_stored_language_that_makes_no_sense_falls_back_to_detection(
    session,
) -> None:
    """Nonsense must not fail every job forever — detection is a working
    answer, and the warning says what happened."""
    from app.db.models import AppSetting

    session.add(AppSetting(key="transcription_language", value="Klingon"))
    await session.commit()

    effective = await effective_settings(session)
    assert effective.transcription_language is None


# --- speed on a machine with no GPU ------------------------------------------


async def test_turbo_is_offered_and_recommended(client) -> None:
    """The agency has no GPU, so the only route to Large-grade Hindi is the
    turbo variant: near the same quality, roughly five times the speed."""
    payload = (await client.get("/api/settings")).json()
    model = [d for d in payload["definitions"] if d["key"] == "faster_whisper_model"][0]

    assert "large-v3-turbo" in model["choices"]
    assert "recommended" in model["choice_labels"]["large-v3-turbo"].lower()
    # Every choice must still be nameable, or the dropdown shows raw codes.
    assert set(model["choices"]) <= set(model["choice_labels"])


def test_batching_is_on_by_default() -> None:
    """Two to four times faster on a CPU for identical output — there is no
    reason for it to be opt-in."""
    from app.config import Settings

    assert Settings().faster_whisper_batch_size > 1


# --- switching engine from the screen ----------------------------------------


async def test_the_engine_can_be_switched_without_a_restart(session) -> None:
    """The reason this is a setting rather than a second copy of the project:
    put the same reel through both engines and compare, in one app.

    This is also the regression test for a real bug — providers were cached by
    name, so the second call returned the first engine no matter what the screen
    said.
    """
    from app.services.transcription import get_transcription_provider

    await update_settings(session, {"transcription_provider": "faster_whisper"})
    first = get_transcription_provider(await effective_settings(session))
    assert first.name == "faster_whisper"

    await update_settings(session, {"transcription_provider": "sarvam"})
    second = get_transcription_provider(await effective_settings(session))
    assert second.name == "sarvam"


async def test_a_changed_model_reaches_a_freshly_built_engine(session) -> None:
    """The other half of the same bug: a cached provider kept the settings it
    was born with, so choosing a bigger model changed nothing."""
    from app.services.transcription import get_transcription_provider

    await update_settings(
        session, {"transcription_provider": "faster_whisper", "faster_whisper_model": "small"}
    )
    assert get_transcription_provider(await effective_settings(session)).model_name == "small"

    await update_settings(session, {"faster_whisper_model": "large-v3-turbo"})
    provider = get_transcription_provider(await effective_settings(session))
    assert provider.model_name == "large-v3-turbo"


async def test_only_real_engines_are_offered(client) -> None:
    payload = (await client.get("/api/settings")).json()
    engine = [d for d in payload["definitions"] if d["key"] == "transcription_provider"][0]

    assert set(engine["choices"]) == {"faster_whisper", "sarvam"}
    assert "stub" not in engine["choices"]  # a test fixture, not a choice
    # The label has to warn about the upload; the help alone is too easy to skip.
    assert "uploaded" in engine["choice_labels"]["sarvam"]


async def test_switching_engine_is_admin_only(client) -> None:
    """It changes where client audio goes. Not a member's decision."""
    response = await client.patch(
        "/api/settings", json={"values": {"transcription_provider": "sarvam"}}
    )
    assert response.status_code == 403


async def test_an_invented_engine_is_refused(session) -> None:
    with pytest.raises(AppError):
        await update_settings(session, {"transcription_provider": "chatgpt"})
