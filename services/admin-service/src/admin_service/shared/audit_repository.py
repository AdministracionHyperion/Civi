from __future__ import annotations

from dataclasses import dataclass, field
from datetime import UTC, datetime
from itertools import count
import os
from threading import Lock
from typing import Protocol


@dataclass
class AdminAuditEvent:
    id: int
    actor: str
    action: str
    target: str
    outcome: str = "success"
    detail: str | None = None
    created_at: str = field(default_factory=lambda: datetime.now(UTC).isoformat(timespec="seconds"))


class AdminAuditRepository(Protocol):
    def record(
        self,
        *,
        actor: str,
        action: str,
        target: str,
        outcome: str = "success",
        detail: str | None = None,
    ) -> AdminAuditEvent:
        ...

    def list_events(self, *, limit: int = 100) -> list[AdminAuditEvent]:
        ...


class InMemoryAdminAuditRepository:
    def __init__(self) -> None:
        self._records: list[AdminAuditEvent] = []
        self._ids = count(1)
        self._lock = Lock()

    def record(
        self,
        *,
        actor: str,
        action: str,
        target: str,
        outcome: str = "success",
        detail: str | None = None,
    ) -> AdminAuditEvent:
        with self._lock:
            record = AdminAuditEvent(
                id=next(self._ids),
                actor=actor,
                action=action,
                target=target,
                outcome=outcome,
                detail=detail,
            )
            self._records.append(record)
            return record

    def list_events(self, *, limit: int = 100) -> list[AdminAuditEvent]:
        return list(reversed(self._records))[:limit]


def repository_from_env() -> AdminAuditRepository:
    mode = os.getenv("ADMIN_AUDIT_REPOSITORY_MODE", "memory").strip().lower()
    if mode in {"", "memory"}:
        return InMemoryAdminAuditRepository()
    if mode == "sql":
        database_url = os.getenv("ADMIN_DATABASE_URL", "").strip()
        if not database_url:
            raise RuntimeError("ADMIN_DATABASE_URL is required when ADMIN_AUDIT_REPOSITORY_MODE=sql")
        from admin_service.adapters.outbound.sql_audit_repository import SqlAdminAuditRepository

        auto_create = os.getenv("ADMIN_AUTO_CREATE_SCHEMA", "").strip().lower() in {"1", "true", "yes"}
        return SqlAdminAuditRepository(database_url, create_schema=auto_create)
    raise RuntimeError(f"unsupported admin audit repository mode: {mode}")


repository = repository_from_env()
