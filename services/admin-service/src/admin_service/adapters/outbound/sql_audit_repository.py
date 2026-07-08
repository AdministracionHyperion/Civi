from __future__ import annotations

from datetime import UTC, datetime

from sqlalchemy import Column, Integer, MetaData, String, Table, create_engine, select
from sqlalchemy.engine import Engine

from admin_service.shared.audit_repository import AdminAuditEvent

metadata = MetaData()

admin_audit_events = Table(
    "admin_audit_events",
    metadata,
    Column("id", Integer, primary_key=True, autoincrement=True),
    Column("actor", String(128), nullable=False, index=True),
    Column("action", String(128), nullable=False, index=True),
    Column("target", String(128), nullable=False),
    Column("outcome", String(32), nullable=False),
    Column("detail", String(1024), nullable=True),
    Column("created_at", String(64), nullable=False, index=True),
)


class SqlAdminAuditRepository:
    def __init__(self, database_url: str, *, create_schema: bool = False) -> None:
        self.engine: Engine = create_engine(database_url, future=True)
        if create_schema:
            metadata.create_all(self.engine)

    def record(
        self,
        *,
        actor: str,
        action: str,
        target: str,
        outcome: str = "success",
        detail: str | None = None,
    ) -> AdminAuditEvent:
        created_at = datetime.now(UTC).isoformat(timespec="seconds")
        with self.engine.begin() as conn:
            result = conn.execute(
                admin_audit_events.insert().values(
                    actor=actor,
                    action=action,
                    target=target,
                    outcome=outcome,
                    detail=detail,
                    created_at=created_at,
                )
            )
            event_id = int(result.inserted_primary_key[0])
        return AdminAuditEvent(
            id=event_id,
            actor=actor,
            action=action,
            target=target,
            outcome=outcome,
            detail=detail,
            created_at=created_at,
        )

    def list_events(self, *, limit: int = 100) -> list[AdminAuditEvent]:
        stmt = select(admin_audit_events).order_by(admin_audit_events.c.id.desc()).limit(limit)
        with self.engine.begin() as conn:
            rows = conn.execute(stmt).mappings().all()
        return [_event_from_row(row) for row in rows]


def _event_from_row(row) -> AdminAuditEvent:
    return AdminAuditEvent(
        id=int(row["id"]),
        actor=str(row["actor"]),
        action=str(row["action"]),
        target=str(row["target"]),
        outcome=str(row["outcome"]),
        detail=row["detail"],
        created_at=str(row["created_at"]),
    )
