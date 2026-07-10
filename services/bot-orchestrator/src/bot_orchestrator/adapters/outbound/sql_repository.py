from __future__ import annotations

import json
from datetime import datetime, timedelta, timezone
from typing import Any

from sqlalchemy import Column, MetaData, String, Table, Text, create_engine, select, text, update
from sqlalchemy.engine import Engine

from bot_orchestrator.shared.consult_jobs import ConsultJob, ConsultJobStatus

metadata = MetaData()

bot_consult_jobs = Table(
    "bot_consult_jobs",
    metadata,
    Column("job_id", String(32), primary_key=True),
    Column("user_key", String(128), nullable=False, index=True),
    Column("channel", String(32), nullable=False),
    Column("intent", String(32), nullable=False),
    Column("placa", String(16), nullable=True),
    Column("documento", String(32), nullable=True),
    Column("ciudad", String(64), nullable=True),
    Column("status", String(32), nullable=False, index=True),
    Column("created_at", String(64), nullable=False),
    Column("completed_at", String(64), nullable=True),
    Column("result", Text, nullable=True),
    Column("error_message", Text, nullable=True),
)

bot_pending_appointments = Table(
    "bot_pending_appointments",
    metadata,
    Column("user_key", String(128), primary_key=True),
    Column("channel", String(32), nullable=False),
    Column("procedure", String(32), nullable=False),
    Column("created_at", String(64), nullable=False),
)


class SqlConsultJobRepository:
    MAX_PENDING_JOBS = 20

    def __init__(self, database_url: str, *, create_schema: bool = False) -> None:
        self.engine: Engine = create_engine(database_url, future=True)
        if create_schema:
            self._create_schema()

    def _create_schema(self) -> None:
        if self.engine.dialect.name == "postgresql":
            with self.engine.begin() as conn:
                conn.execute(text("SELECT pg_advisory_xact_lock(hashtext('civi_bot_consult_schema'))"))
                metadata.create_all(conn)
                conn.execute(
                    text(
                        "ALTER TABLE bot_consult_jobs "
                        "ADD COLUMN IF NOT EXISTS ciudad VARCHAR(64)"
                    )
                )
            return

        metadata.create_all(self.engine)
        if self.engine.dialect.name == "sqlite":
            with self.engine.begin() as conn:
                cols = conn.execute(text("PRAGMA table_info(bot_consult_jobs)")).fetchall()
                names = {str(row[1]) for row in cols}
                if "ciudad" not in names:
                    conn.execute(text("ALTER TABLE bot_consult_jobs ADD COLUMN ciudad VARCHAR(64)"))

    def count_pending(self) -> int:
        stmt = select(bot_consult_jobs).where(bot_consult_jobs.c.status == ConsultJobStatus.PENDING.value)
        with self.engine.begin() as conn:
            rows = conn.execute(stmt).mappings().all()
            return len(rows)

    def enqueue(self, job: ConsultJob) -> tuple[ConsultJob, int]:
        with self.engine.begin() as conn:
            pending_count = conn.execute(
                select(bot_consult_jobs).where(bot_consult_jobs.c.status == ConsultJobStatus.PENDING.value)
            ).mappings().fetchall()
            position = len(pending_count) + 1
            if len(pending_count) >= self.MAX_PENDING_JOBS:
                raise RuntimeError(
                    f"La cola de consultas esta llena ({self.MAX_PENDING_JOBS} maximo). "
                    "Intentalo de nuevo en un momento."
                )
            conn.execute(
                bot_consult_jobs.insert().values(
                    job_id=job.job_id,
                    user_key=job.user_key,
                    channel=job.channel,
                    intent=job.intent,
                    placa=job.placa,
                    documento=job.documento,
                    ciudad=job.ciudad,
                    status=ConsultJobStatus.PENDING.value,
                    created_at=job.created_at,
                    completed_at=None,
                    result=None,
                    error_message=None,
                )
            )
        job.status = ConsultJobStatus.PENDING
        return job, position

    def dequeue_next_pending(self) -> ConsultJob | None:
        with self.engine.begin() as conn:
            row = conn.execute(
                select(bot_consult_jobs)
                .where(bot_consult_jobs.c.status == ConsultJobStatus.PENDING.value)
                .order_by(bot_consult_jobs.c.created_at)
                .limit(1)
            ).mappings().first()

            if row is None:
                return None

            updated = conn.execute(
                update(bot_consult_jobs)
                .where(bot_consult_jobs.c.job_id == row["job_id"])
                .where(bot_consult_jobs.c.status == ConsultJobStatus.PENDING.value)
                .values(status=ConsultJobStatus.PROCESSING.value)
            )
            if updated.rowcount != 1:
                return None

        return _row_to_job(row, status=ConsultJobStatus.PROCESSING)

    def mark_done(self, job_id: str, result: dict) -> None:
        completed_at = datetime.now(timezone.utc).isoformat()
        with self.engine.begin() as conn:
            conn.execute(
                update(bot_consult_jobs)
                .where(bot_consult_jobs.c.job_id == job_id)
                .values(
                    status=ConsultJobStatus.DONE.value,
                    result=json.dumps(result, ensure_ascii=False),
                    completed_at=completed_at,
                )
            )

    def mark_failed(self, job_id: str, error_message: str) -> None:
        completed_at = datetime.now(timezone.utc).isoformat()
        with self.engine.begin() as conn:
            conn.execute(
                update(bot_consult_jobs)
                .where(bot_consult_jobs.c.job_id == job_id)
                .values(
                    status=ConsultJobStatus.FAILED.value,
                    error_message=error_message[:2000],
                    completed_at=completed_at,
                )
            )

    def get(self, job_id: str) -> ConsultJob | None:
        with self.engine.begin() as conn:
            row = conn.execute(
                select(bot_consult_jobs).where(bot_consult_jobs.c.job_id == job_id)
            ).mappings().first()
        if row is None:
            return None
        return _row_to_job(row)

    def get_position(self, job_id: str) -> int | None:
        with self.engine.begin() as conn:
            row = conn.execute(
                select(bot_consult_jobs).where(bot_consult_jobs.c.job_id == job_id)
            ).mappings().first()
            if row is None or row["status"] != ConsultJobStatus.PENDING.value:
                return None

            count_row = conn.execute(
                select(bot_consult_jobs)
                .where(bot_consult_jobs.c.status == ConsultJobStatus.PENDING.value)
                .where(bot_consult_jobs.c.created_at <= row["created_at"])
            ).mappings().fetchall()
            return len(count_row)

    def find_active_for_user(
        self, *, user_key: str, intent: str, max_age_seconds: int
    ) -> tuple[ConsultJob, int] | None:
        """Return (job, position) if there's an active (pending/processing) job for this user+intent
        created within max_age_seconds, or None."""
        cutoff = (datetime.now(timezone.utc) - timedelta(seconds=max_age_seconds)).isoformat()
        with self.engine.begin() as conn:
            row = conn.execute(
                select(bot_consult_jobs)
                .where(bot_consult_jobs.c.user_key == user_key)
                .where(bot_consult_jobs.c.intent == intent)
                .where(bot_consult_jobs.c.status.in_([ConsultJobStatus.PENDING.value, ConsultJobStatus.PROCESSING.value]))
                .where(bot_consult_jobs.c.created_at >= cutoff)
                .order_by(bot_consult_jobs.c.created_at)
                .limit(1)
            ).mappings().first()
            if row is None:
                return None
            status = ConsultJobStatus(row["status"])
            position: int = 1
            if status == ConsultJobStatus.PENDING:
                pos_rows = conn.execute(
                    select(bot_consult_jobs)
                    .where(bot_consult_jobs.c.status == ConsultJobStatus.PENDING.value)
                    .where(bot_consult_jobs.c.created_at <= row["created_at"])
                ).mappings().fetchall()
                position = len(pos_rows)
            job = _row_to_job(row)
            return job, position

    def reap_stuck_jobs(self, *, max_processing_seconds: int) -> list[ConsultJob]:
        """Mark processing jobs older than max_processing_seconds as failed. Returns the reaped jobs."""
        cutoff = (datetime.now(timezone.utc) - timedelta(seconds=max_processing_seconds)).isoformat()
        error_msg = f"Stuck in processing for >{max_processing_seconds}s"
        completed_at = datetime.now(timezone.utc).isoformat()
        with self.engine.begin() as conn:
            rows = conn.execute(
                select(bot_consult_jobs)
                .where(bot_consult_jobs.c.status == ConsultJobStatus.PROCESSING.value)
                .where(bot_consult_jobs.c.created_at <= cutoff)
            ).mappings().all()
            if not rows:
                return []

            job_ids = [row["job_id"] for row in rows]
            conn.execute(
                update(bot_consult_jobs)
                .where(bot_consult_jobs.c.job_id.in_(job_ids))
                .where(bot_consult_jobs.c.status == ConsultJobStatus.PROCESSING.value)
                .values(
                    status=ConsultJobStatus.FAILED.value,
                    error_message=error_msg[:2000],
                    completed_at=completed_at,
                )
            )
        return [_row_to_job(row, status=ConsultJobStatus.FAILED) for row in rows]

    def clear_all(self) -> None:
        conn = self.engine.connect()
        try:
            conn.execute(bot_consult_jobs.delete())
            conn.commit()
        finally:
            conn.close()


def _row_to_job(row, *, status: ConsultJobStatus | None = None) -> ConsultJob:
    raw_result = row.get("result")
    result = None
    if raw_result:
        try:
            result = json.loads(raw_result) if isinstance(raw_result, str) else raw_result
        except (json.JSONDecodeError, TypeError):
            result = {"raw": str(raw_result)}

    return ConsultJob(
        job_id=str(row["job_id"]),
        user_key=str(row["user_key"]),
        channel=str(row["channel"]),
        intent=str(row["intent"]),
        placa=str(row["placa"]) if row.get("placa") else None,
        documento=str(row["documento"]) if row.get("documento") else None,
        ciudad=str(row["ciudad"]) if row.get("ciudad") else None,
        status=status or ConsultJobStatus(str(row["status"])),
        created_at=str(row["created_at"]),
        completed_at=str(row["completed_at"]) if row.get("completed_at") else None,
        result=result,
        error_message=str(row["error_message"]) if row.get("error_message") else None,
    )


class SqlPendingAppointmentStore:
    """SQL-backed pending appointment store shared between API and worker processes."""

    def __init__(self, database_url: str, *, create_schema: bool = False) -> None:
        self.engine: Engine = create_engine(database_url, future=True)
        if create_schema:
            self._create_schema()

    def _create_schema(self) -> None:
        if self.engine.dialect.name == "postgresql":
            with self.engine.begin() as conn:
                conn.execute(text("SELECT pg_advisory_xact_lock(hashtext('civi_bot_pending_schema'))"))
                metadata.create_all(conn)
            return
        metadata.create_all(self.engine)

    def save(self, *, user_key: str, channel: str, procedure: str) -> None:
        created_at = datetime.now(timezone.utc).isoformat()
        with self.engine.begin() as conn:
            if self.engine.dialect.name == "postgresql":
                from sqlalchemy.dialects.postgresql import insert as pg_insert

                stmt = pg_insert(bot_pending_appointments).values(
                    user_key=user_key,
                    channel=channel,
                    procedure=procedure,
                    created_at=created_at,
                )
                stmt = stmt.on_conflict_do_update(
                    index_elements=["user_key"],
                    set_={"procedure": procedure, "channel": channel, "created_at": created_at},
                )
                conn.execute(stmt)
            else:
                conn.execute(
                    bot_pending_appointments.delete().where(bot_pending_appointments.c.user_key == user_key)
                )
                conn.execute(
                    bot_pending_appointments.insert().values(
                        user_key=user_key,
                        channel=channel,
                        procedure=procedure,
                        created_at=created_at,
                    )
                )

    def get_and_clear(self, *, user_key: str) -> dict[str, Any] | None:
        with self.engine.begin() as conn:
            row = conn.execute(
                select(bot_pending_appointments).where(bot_pending_appointments.c.user_key == user_key)
            ).mappings().first()
            if row is None:
                return None
            conn.execute(
                bot_pending_appointments.delete().where(bot_pending_appointments.c.user_key == user_key)
            )
        return {
            "user_key": str(row["user_key"]),
            "channel": str(row["channel"]),
            "procedure": str(row["procedure"]),
        }