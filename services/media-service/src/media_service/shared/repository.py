from __future__ import annotations

from dataclasses import dataclass, field
from datetime import UTC, datetime
from hashlib import sha256
from itertools import count
import os
from threading import Lock
from typing import Protocol


@dataclass
class MediaProcessingJob:
    id: int
    media_kind: str
    content_type: str
    size_bytes: int
    media_ref_hash: str
    provider_mode: str
    status: str
    output_length: int = 0
    error: str | None = None
    created_at: str = field(default_factory=lambda: datetime.now(UTC).isoformat(timespec="seconds"))


class MediaRepository(Protocol):
    def record_job(
        self,
        *,
        media_kind: str,
        media_ref: str,
        content_type: str,
        size_bytes: int,
        provider_mode: str,
        status: str,
        output_text: str | None = None,
        error: str | None = None,
    ) -> MediaProcessingJob:
        ...


class InMemoryMediaRepository:
    def __init__(self) -> None:
        self._records: dict[int, MediaProcessingJob] = {}
        self._ids = count(1)
        self._lock = Lock()

    def record_job(
        self,
        *,
        media_kind: str,
        media_ref: str,
        content_type: str,
        size_bytes: int,
        provider_mode: str,
        status: str,
        output_text: str | None = None,
        error: str | None = None,
    ) -> MediaProcessingJob:
        with self._lock:
            job = MediaProcessingJob(
                id=next(self._ids),
                media_kind=media_kind,
                content_type=content_type,
                size_bytes=size_bytes,
                media_ref_hash=media_ref_hash(media_ref),
                provider_mode=provider_mode,
                status=status,
                output_length=len(output_text or ""),
                error=error,
            )
            self._records[job.id] = job
            return job


def repository_from_env() -> MediaRepository:
    mode = os.getenv("MEDIA_REPOSITORY_MODE", "memory").strip().lower()
    if mode in {"", "memory"}:
        return InMemoryMediaRepository()
    if mode == "sql":
        database_url = os.getenv("MEDIA_DATABASE_URL", "").strip()
        if not database_url:
            raise RuntimeError("MEDIA_DATABASE_URL is required when MEDIA_REPOSITORY_MODE=sql")
        from media_service.adapters.outbound.sql_repository import SqlMediaRepository

        auto_create = os.getenv("MEDIA_AUTO_CREATE_SCHEMA", "").strip().lower() in {"1", "true", "yes"}
        return SqlMediaRepository(database_url, create_schema=auto_create)
    raise RuntimeError(f"unsupported media repository mode: {mode}")


def media_ref_hash(value: str) -> str:
    return sha256(str(value or "").strip().encode("utf-8")).hexdigest()


repository = repository_from_env()
