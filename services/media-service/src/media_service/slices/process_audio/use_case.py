from __future__ import annotations

from media_service.adapters.outbound.audio_transcriber import (
    AudioTranscriber,
    audio_transcriber_from_env,
)
from media_service.shared.policy import normalize_content_type
from media_service.shared.repository import MediaRepository, repository
from media_service.slices.validate_media.schemas import ValidateMediaRequest
from media_service.slices.validate_media.use_case import validate_media

from .schemas import ProcessAudioRequest, ProcessAudioResponse


async def process_audio(
    payload: ProcessAudioRequest,
    *,
    transcriber: AudioTranscriber | None = None,
    media_repository: MediaRepository | None = None,
) -> ProcessAudioResponse:
    active_repository = media_repository or repository
    content_type = normalize_content_type(payload.content_type) or payload.content_type
    validation = await validate_media(
        ValidateMediaRequest(content_type=content_type, size_bytes=payload.size_bytes)
    )
    if not validation.success or validation.media_kind != "audio":
        error = validation.error or "not audio"
        job = active_repository.record_job(
            media_kind=validation.media_kind or "audio",
            media_ref=payload.media_ref,
            content_type=content_type,
            size_bytes=payload.size_bytes,
            provider_mode="validation",
            status="failed",
            error=error,
        )
        return ProcessAudioResponse(success=False, job_id=job.id, error=error)
    result = await (transcriber or audio_transcriber_from_env()).transcribe(
        media_ref=payload.media_ref,
        content_type=content_type,
        content_base64=payload.content_base64,
    )
    transcript = result.get("transcript")
    provider_mode = str(result.get("provider_mode", "unknown"))
    job = active_repository.record_job(
        media_kind="audio",
        media_ref=payload.media_ref,
        content_type=content_type,
        size_bytes=payload.size_bytes,
        provider_mode=provider_mode,
        status="completed",
        output_text=transcript if isinstance(transcript, str) else None,
    )
    return ProcessAudioResponse(
        success=True,
        job_id=job.id,
        transcript=transcript if isinstance(transcript, str) else None,
        provider_mode=provider_mode,
    )
