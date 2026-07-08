from __future__ import annotations

from datetime import UTC, datetime

from sqlalchemy import Column, Integer, MetaData, String, Table, create_engine
from sqlalchemy.engine import Engine

from media_service.shared.repository import MediaProcessingJob, media_ref_hash

metadata = MetaData()

media_processing_jobs = Table(
    "media_processing_jobs",
    metadata,
    Column("id", Integer, primary_key=True, autoincrement=True),
    Column("media_kind", String(32), nullable=False, index=True),
    Column("content_type", String(128), nullable=False),
    Column("size_bytes", Integer, nullable=False),
    Column("media_ref_hash", String(128), nullable=False, index=True),
    Column("provider_mode", String(64), nullable=False),
    Column("status", String(32), nullable=False, index=True),
    Column("output_length", Integer, nullable=False),
    Column("error", String(512), nullable=True),
    Column("created_at", String(64), nullable=False),
)


class SqlMediaRepository:
    def __init__(self, database_url: str, *, create_schema: bool = False) -> None:
        self.engine: Engine = create_engine(database_url, future=True)
        if create_schema:
            metadata.create_all(self.engine)

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
        created_at = datetime.now(UTC).isoformat(timespec="seconds")
        output_length = len(output_text or "")
        ref_hash = media_ref_hash(media_ref)
        with self.engine.begin() as conn:
            result = conn.execute(
                media_processing_jobs.insert().values(
                    media_kind=media_kind,
                    content_type=content_type,
                    size_bytes=size_bytes,
                    media_ref_hash=ref_hash,
                    provider_mode=provider_mode,
                    status=status,
                    output_length=output_length,
                    error=error,
                    created_at=created_at,
                )
            )
            job_id = int(result.inserted_primary_key[0])
        return MediaProcessingJob(
            id=job_id,
            media_kind=media_kind,
            content_type=content_type,
            size_bytes=size_bytes,
            media_ref_hash=ref_hash,
            provider_mode=provider_mode,
            status=status,
            output_length=output_length,
            error=error,
            created_at=created_at,
        )
