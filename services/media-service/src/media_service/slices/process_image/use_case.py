from __future__ import annotations

from media_service.adapters.outbound.image_vision import (
    ImageVisionExtractor,
    image_vision_from_env,
)
from media_service.shared.repository import MediaRepository, repository
from media_service.slices.validate_media.schemas import ValidateMediaRequest
from media_service.slices.validate_media.use_case import validate_media

from .schemas import ProcessImageRequest, ProcessImageResponse


async def process_image(
    payload: ProcessImageRequest,
    *,
    extractor: ImageVisionExtractor | None = None,
    media_repository: MediaRepository | None = None,
) -> ProcessImageResponse:
    active_repository = media_repository or repository
    validation = await validate_media(
        ValidateMediaRequest(content_type=payload.content_type, size_bytes=payload.size_bytes)
    )
    if not validation.success or validation.media_kind != "image":
        error = validation.error or "not image"
        job = active_repository.record_job(
            media_kind=validation.media_kind or "image",
            media_ref=payload.media_ref,
            content_type=payload.content_type,
            size_bytes=payload.size_bytes,
            provider_mode="validation",
            status="failed",
            error=error,
        )
        return ProcessImageResponse(success=False, job_id=job.id, error=error)
    result = await (extractor or image_vision_from_env()).extract_text(
        media_ref=payload.media_ref,
        content_type=payload.content_type,
    )
    extracted_text = result.get("extracted_text")
    provider_mode = str(result.get("provider_mode", "unknown"))
    job = active_repository.record_job(
        media_kind="image",
        media_ref=payload.media_ref,
        content_type=payload.content_type,
        size_bytes=payload.size_bytes,
        provider_mode=provider_mode,
        status="completed",
        output_text=extracted_text if isinstance(extracted_text, str) else None,
    )
    return ProcessImageResponse(
        success=True,
        job_id=job.id,
        extracted_text=extracted_text,
        provider_mode=provider_mode,
    )
