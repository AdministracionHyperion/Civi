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


def normalize_content_type(content_type: str) -> str:
    """Strip parameters (e.g. codecs) and lowercase the MIME type."""
    raw = (content_type or "").strip().lower()
    if not raw:
        return ""
    return raw.split(";", 1)[0].strip()


def media_kind(content_type: str) -> str | None:
    normalized = normalize_content_type(content_type)
    if normalized in ALLOWED_AUDIO_TYPES:
        return "audio"
    if normalized in ALLOWED_IMAGE_TYPES:
        return "image"
    return None
