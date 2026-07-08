from __future__ import annotations

ALLOWED_AUDIO_TYPES = frozenset({
    "audio/ogg",
    "audio/mpeg",
    "audio/mp4",
    "audio/wav",
    "audio/webm",
})

ALLOWED_IMAGE_TYPES = frozenset({
    "image/jpeg",
    "image/png",
    "image/webp",
})

MAX_MEDIA_BYTES = 15 * 1024 * 1024


def media_kind(content_type: str) -> str | None:
    normalized = content_type.strip().lower()
    if normalized in ALLOWED_AUDIO_TYPES:
        return "audio"
    if normalized in ALLOWED_IMAGE_TYPES:
        return "image"
    return None
