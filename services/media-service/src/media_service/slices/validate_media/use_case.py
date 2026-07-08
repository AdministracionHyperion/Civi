from __future__ import annotations

from media_service.shared.policy import MAX_MEDIA_BYTES, media_kind

from .schemas import ValidateMediaRequest, ValidateMediaResponse


async def validate_media(payload: ValidateMediaRequest) -> ValidateMediaResponse:
    kind = media_kind(payload.content_type)
    if kind is None:
        return ValidateMediaResponse(success=False, error="unsupported content type")
    if payload.size_bytes > MAX_MEDIA_BYTES:
        return ValidateMediaResponse(success=False, media_kind=kind, error="media too large")
    return ValidateMediaResponse(success=True, media_kind=kind)
