import pytest
import httpx
from fastapi.testclient import TestClient

from media_service.adapters.outbound.audio_transcriber import OpenAIUrlAudioTranscriber, audio_transcriber_from_env
from media_service.adapters.outbound.image_vision import (
    OpenAICompatibleImageVisionExtractor,
    OpenAIImageVisionExtractor,
    image_vision_from_env,
)
from media_service.adapters.outbound.sql_repository import SqlMediaRepository
from media_service.main import app
from media_service.shared.repository import InMemoryMediaRepository
from media_service.slices.process_audio.schemas import ProcessAudioRequest
from media_service.slices.process_audio.use_case import process_audio
from media_service.slices.process_image.schemas import ProcessImageRequest
from media_service.slices.process_image.use_case import process_image
from media_service.slices.validate_media.schemas import ValidateMediaRequest
from media_service.slices.validate_media.use_case import validate_media


@pytest.mark.asyncio
async def test_validate_allowed_audio() -> None:
    result = await validate_media(ValidateMediaRequest(content_type=" AUDIO/OGG ", size_bytes=1000))

    assert result.success
    assert result.media_kind == "audio"


@pytest.mark.asyncio
async def test_reject_large_media() -> None:
    result = await validate_media(ValidateMediaRequest(content_type="image/png", size_bytes=20 * 1024 * 1024))

    assert not result.success
    assert result.error == "media too large"


@pytest.mark.asyncio
async def test_process_audio_disabled_provider_mode() -> None:
    repo = InMemoryMediaRepository()
    result = await process_audio(
        ProcessAudioRequest(content_type="audio/ogg", size_bytes=1000, media_ref="media-1"),
        media_repository=repo,
    )

    assert result.success
    assert result.job_id == 1
    assert result.provider_mode == "disabled_until_provider_configured"


@pytest.mark.asyncio
async def test_process_image_disabled_provider_mode() -> None:
    repo = InMemoryMediaRepository()
    result = await process_image(
        ProcessImageRequest(content_type="image/png", size_bytes=1000, media_ref="media-1"),
        media_repository=repo,
    )

    assert result.success
    assert result.job_id == 1
    assert result.provider_mode == "disabled_until_provider_configured"


@pytest.mark.asyncio
async def test_process_audio_records_failed_validation_job() -> None:
    repo = InMemoryMediaRepository()

    result = await process_audio(
        ProcessAudioRequest(content_type="application/pdf", size_bytes=1000, media_ref="media-1"),
        media_repository=repo,
    )

    assert not result.success
    assert result.job_id == 1
    assert result.error == "unsupported content type"


def test_media_provider_modes_fail_closed(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("MEDIA_AUDIO_PROVIDER_MODE", "unknown-audio")
    monkeypatch.setenv("MEDIA_IMAGE_PROVIDER_MODE", "unknown-image")

    with pytest.raises(RuntimeError, match="unsupported audio provider mode"):
        audio_transcriber_from_env()
    with pytest.raises(RuntimeError, match="unsupported image provider mode"):
        image_vision_from_env()


def test_openai_media_modes_require_credentials(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("MEDIA_AUDIO_PROVIDER_MODE", "openai")
    monkeypatch.setenv("MEDIA_IMAGE_PROVIDER_MODE", "openai")
    monkeypatch.delenv("OPENAI_API_KEY", raising=False)
    monkeypatch.delenv("OPENAI_AUDIO_TRANSCRIPTION_MODEL", raising=False)
    monkeypatch.delenv("OPENAI_IMAGE_VISION_MODEL", raising=False)

    with pytest.raises(RuntimeError, match="OPENAI_API_KEY"):
        audio_transcriber_from_env()
    with pytest.raises(RuntimeError, match="OPENAI_API_KEY"):
        image_vision_from_env()


def test_deepseek_image_mode_requires_credentials(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("MEDIA_IMAGE_PROVIDER_MODE", "deepseek")
    monkeypatch.delenv("DEEPSEEK_API_KEY", raising=False)

    with pytest.raises(RuntimeError, match="DEEPSEEK"):
        image_vision_from_env()


@pytest.mark.asyncio
async def test_openai_audio_transcriber_uses_media_url_without_live_call() -> None:
    requests: list[httpx.Request] = []

    async def handler(request: httpx.Request) -> httpx.Response:
        requests.append(request)
        if str(request.url) == "https://media.example.test/audio.ogg":
            return httpx.Response(200, content=b"audio-bytes")
        return httpx.Response(200, json={"text": "transcripcion de prueba"})

    transcriber = OpenAIUrlAudioTranscriber(
        api_key="key-test",
        model="audio-model-test",
        base_url="https://api.example.test",
        transport=httpx.MockTransport(handler),
    )

    result = await transcriber.transcribe(
        media_ref="https://media.example.test/audio.ogg",
        content_type="audio/ogg",
    )

    assert result == {"provider_mode": "openai", "transcript": "transcripcion de prueba"}
    assert str(requests[1].url) == "https://api.example.test/v1/audio/transcriptions"
    assert requests[1].headers["Authorization"] == "Bearer key-test"


@pytest.mark.asyncio
async def test_openai_image_vision_uses_responses_api_without_live_call() -> None:
    requests: list[httpx.Request] = []

    async def handler(request: httpx.Request) -> httpx.Response:
        requests.append(request)
        return httpx.Response(200, json={"output_text": "ABC123"})

    extractor = OpenAIImageVisionExtractor(
        api_key="key-test",
        model="vision-model-test",
        base_url="https://api.example.test",
        transport=httpx.MockTransport(handler),
    )

    result = await extractor.extract_text(
        media_ref="https://media.example.test/image.png",
        content_type="image/png",
    )

    assert result == {"provider_mode": "openai", "extracted_text": "ABC123"}
    assert str(requests[0].url) == "https://api.example.test/v1/responses"
    assert requests[0].headers["Authorization"] == "Bearer key-test"
    assert b"https://media.example.test/image.png" in requests[0].read()


@pytest.mark.asyncio
async def test_openai_compatible_image_vision_uses_chat_completion_without_live_call() -> None:
    requests: list[httpx.Request] = []

    async def handler(request: httpx.Request) -> httpx.Response:
        requests.append(request)
        return httpx.Response(200, json={"choices": [{"message": {"content": "ABC123"}}]})

    extractor = OpenAICompatibleImageVisionExtractor(
        provider_mode="deepseek",
        api_key="key-test",
        model="deepseek-vision-test",
        base_url="https://api.deepseek.test/v1",
        transport=httpx.MockTransport(handler),
    )

    result = await extractor.extract_text(
        media_ref="https://media.example.test/image.png",
        content_type="image/png",
    )

    assert result == {"provider_mode": "deepseek", "extracted_text": "ABC123"}
    assert str(requests[0].url) == "https://api.deepseek.test/v1/chat/completions"
    assert requests[0].headers["Authorization"] == "Bearer key-test"
    body = requests[0].read()
    assert b"deepseek-vision-test" in body
    assert b"https://media.example.test/image.png" in body


def test_media_validate_requires_token(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("INTERNAL_SERVICE_TOKEN", "internal-test-token")
    client = TestClient(app)
    payload = {"content_type": "audio/ogg", "size_bytes": 1000}

    assert client.post("/internal/media/validate", json=payload).status_code == 401

    response = client.post(
        "/internal/media/validate",
        json=payload,
        headers={"Authorization": "Bearer internal-test-token"},
    )
    assert response.status_code == 200
    assert response.json()["media_kind"] == "audio"


def test_sql_media_repository_records_job_without_raw_media_ref() -> None:
    repo = SqlMediaRepository("sqlite+pysqlite:///:memory:", create_schema=True)

    job = repo.record_job(
        media_kind="image",
        media_ref="https://signed.example.test/image.png?token=secret",
        content_type="image/png",
        size_bytes=1000,
        provider_mode="openai",
        status="completed",
        output_text="ABC123",
    )

    assert job.id == 1
    assert job.output_length == len("ABC123")
    assert "secret" not in job.media_ref_hash
