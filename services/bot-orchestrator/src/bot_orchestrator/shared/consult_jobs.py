from __future__ import annotations

import datetime
import os
import threading
import uuid
from dataclasses import dataclass
from datetime import timedelta
from enum import Enum
from typing import Any, Protocol


class ConsultJobStatus(str, Enum):
    PENDING = "pending"
    PROCESSING = "processing"
    DONE = "done"
    FAILED = "failed"


@dataclass
class ConsultJob:
    job_id: str
    user_key: str
    channel: str
    intent: str  # "soat", "tecnomecanica", "multas", "runt_profile"
    placa: str | None = None
    documento: str | None = None
    ciudad: str | None = None
    status: ConsultJobStatus = ConsultJobStatus.PENDING
    created_at: str = ""
    completed_at: str | None = None
    result: dict[str, Any] | None = None
    error_message: str | None = None

    def __post_init__(self) -> None:
        if not self.created_at:
            self.created_at = datetime.datetime.now(datetime.timezone.utc).isoformat()


class InMemoryConsultJobRepository:
    """In-memory repository for consult jobs. Used for tests and local dev without SQL."""

    MAX_PENDING_JOBS = 20

    def __init__(self) -> None:
        self._jobs: dict[str, ConsultJob] = {}
        self._order: list[str] = []
        self._lock = threading.Lock()

    def count_pending(self) -> int:
        with self._lock:
            return sum(1 for jid in self._order if self._jobs[jid].status == ConsultJobStatus.PENDING)

    def _count_pending_unsafe(self) -> int:
        """Count pending jobs. Caller must hold self._lock."""
        return sum(1 for jid in self._order if self._jobs[jid].status == ConsultJobStatus.PENDING)

    def enqueue(self, job: ConsultJob) -> tuple[ConsultJob, int]:
        """Enqueue a job. Returns (job, position_in_queue). Raises RuntimeError if queue full."""
        with self._lock:
            pending_count = self._count_pending_unsafe()
            if pending_count >= self.MAX_PENDING_JOBS:
                raise RuntimeError(
                    f"La cola de consultas esta llena ({self.MAX_PENDING_JOBS} maximo). "
                    "Intentalo de nuevo en un momento."
                )
            self._jobs[job.job_id] = job
            self._order.append(job.job_id)
            position = pending_count + 1
            return job, position

    def dequeue_next_pending(self) -> ConsultJob | None:
        """Get the next pending job and mark it as processing. Returns None if no pending jobs."""
        with self._lock:
            for jid in self._order:
                job = self._jobs.get(jid)
                if job and job.status == ConsultJobStatus.PENDING:
                    job.status = ConsultJobStatus.PROCESSING
                    return job
            return None

    def mark_done(self, job_id: str, result: dict[str, Any]) -> None:
        with self._lock:
            job = self._jobs.get(job_id)
            if job:
                job.status = ConsultJobStatus.DONE
                job.result = result
                job.completed_at = datetime.datetime.now(datetime.timezone.utc).isoformat()

    def mark_failed(self, job_id: str, error_message: str) -> None:
        with self._lock:
            job = self._jobs.get(job_id)
            if job:
                job.status = ConsultJobStatus.FAILED
                job.error_message = error_message
                job.completed_at = datetime.datetime.now(datetime.timezone.utc).isoformat()

    def get(self, job_id: str) -> ConsultJob | None:
        with self._lock:
            return self._jobs.get(job_id)

    def get_position(self, job_id: str) -> int | None:
        """Return 1-based position among pending jobs, or None if not pending."""
        with self._lock:
            job = self._jobs.get(job_id)
            if not job or job.status != ConsultJobStatus.PENDING:
                return None
            position = 0
            for jid in self._order:
                j = self._jobs.get(jid)
                if j and j.status == ConsultJobStatus.PENDING:
                    position += 1
                    if jid == job_id:
                        return position
            return None

    def find_active_for_user(
        self, *, user_key: str, intent: str, max_age_seconds: int
    ) -> tuple[ConsultJob, int] | None:
        """Return (job, position) if there's an active (pending/processing) job for this user+intent
        created within max_age_seconds, or None."""
        now = datetime.datetime.now(datetime.timezone.utc)
        cutoff = now - timedelta(seconds=max_age_seconds)
        with self._lock:
            for jid in self._order:
                job = self._jobs.get(jid)
                if not job:
                    continue
                if job.status not in (ConsultJobStatus.PENDING, ConsultJobStatus.PROCESSING):
                    continue
                if job.user_key != user_key or job.intent != intent:
                    continue
                try:
                    created = datetime.datetime.fromisoformat(job.created_at)
                except ValueError:
                    continue
                if created < cutoff:
                    continue
                position = 1
                for other_jid in self._order:
                    other = self._jobs.get(other_jid)
                    if other and other.status == ConsultJobStatus.PENDING:
                        if other_jid == jid:
                            break
                        position += 1
                return job, position
        return None

    def reap_stuck_jobs(self, *, max_processing_seconds: int) -> list[ConsultJob]:
        """Mark processing jobs older than max_processing_seconds as failed. Returns the reaped jobs."""
        now = datetime.datetime.now(datetime.timezone.utc)
        reaped: list[ConsultJob] = []
        with self._lock:
            for jid, job in list(self._jobs.items()):
                if job.status != ConsultJobStatus.PROCESSING:
                    continue
                try:
                    created = datetime.datetime.fromisoformat(job.created_at)
                except ValueError:
                    continue
                if (now - created).total_seconds() > max_processing_seconds:
                    job.status = ConsultJobStatus.FAILED
                    job.error_message = f"Stuck in processing for >{max_processing_seconds}s"
                    job.completed_at = now.isoformat()
                    reaped.append(job)
        return reaped

    def clear_all(self) -> None:
        with self._lock:
            self._jobs.clear()
            self._order.clear()


class ConsultJobRepository(Protocol):
    MAX_PENDING_JOBS: int

    def count_pending(self) -> int: ...
    def enqueue(self, job: ConsultJob) -> tuple[ConsultJob, int]: ...
    def dequeue_next_pending(self) -> ConsultJob | None: ...
    def mark_done(self, job_id: str, result: dict[str, Any]) -> None: ...
    def mark_failed(self, job_id: str, error_message: str) -> None: ...
    def get(self, job_id: str) -> ConsultJob | None: ...
    def get_position(self, job_id: str) -> int | None: ...
    def clear_all(self) -> None: ...
    def find_active_for_user(
        self, *, user_key: str, intent: str, max_age_seconds: int
    ) -> tuple[ConsultJob, int] | None: ...
    def reap_stuck_jobs(self, *, max_processing_seconds: int) -> list[ConsultJob]: ...


def repository_from_env() -> ConsultJobRepository:
    mode = os.getenv("BOT_CONSULT_REPOSITORY_MODE", "sql").strip().lower()
    if mode in {"", "memory"}:
        return InMemoryConsultJobRepository()
    if mode == "sql":
        database_url = os.getenv("BOT_CONSULT_DATABASE_URL", "").strip()
        if not database_url:
            raise RuntimeError("BOT_CONSULT_DATABASE_URL is required when BOT_CONSULT_REPOSITORY_MODE=sql")
        from bot_orchestrator.adapters.outbound.sql_repository import SqlConsultJobRepository

        auto_create = os.getenv("BOT_CONSULT_AUTO_CREATE_SCHEMA", "").strip().lower() in {"1", "true", "yes"}
        return SqlConsultJobRepository(database_url, create_schema=auto_create)
    raise RuntimeError(f"unsupported bot consult repository mode: {mode}")


# Singleton instance — uses env vars
_consult_job_repository: ConsultJobRepository | None = None


def get_consult_job_repository() -> ConsultJobRepository:
    global _consult_job_repository
    if _consult_job_repository is None:
        _consult_job_repository = repository_from_env()
    return _consult_job_repository


def generate_job_id() -> str:
    return uuid.uuid4().hex[:12]


def estimated_wait_seconds(position: int, *, parallelism: int = 1) -> str:
    """Estimate wait time based on queue position (~25s per consult, but jobs run in parallel batches)."""
    cycles = (position - 1) // parallelism  # How many full batches before this job
    seconds = cycles * 25
    if seconds < 60:
        return f"~{seconds} segundos"
    minutes = seconds // 60
    remaining_seconds = seconds % 60
    if remaining_seconds:
        return f"~{minutes} min {remaining_seconds} s"
    return f"~{minutes} minutos"