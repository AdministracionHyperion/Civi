from __future__ import annotations

from datetime import UTC, datetime

from sqlalchemy import Column, Integer, MetaData, String, Table, create_engine, select, text, update
from sqlalchemy.engine import Engine

from notification_service.shared.repository import OutboxMessage, Reminder

metadata = MetaData()

outbox = Table(
    "notification_outbox",
    metadata,
    Column("id", Integer, primary_key=True, autoincrement=True),
    Column("to", String(64), nullable=False),
    Column("body", String(4096), nullable=False),
    Column("channel", String(32), nullable=False),
    Column("status", String(32), nullable=False, index=True),
    Column("created_at", String(64), nullable=False),
    Column("sent_at", String(64), nullable=True),
)

reminders = Table(
    "notification_reminders",
    metadata,
    Column("id", Integer, primary_key=True, autoincrement=True),
    Column("user_key", String(128), nullable=False, index=True),
    Column("to", String(64), nullable=False),
    Column("body", String(4096), nullable=False),
    Column("remind_at", String(64), nullable=False, index=True),
    Column("status", String(32), nullable=False),
    Column("created_at", String(64), nullable=False),
)


class SqlNotificationRepository:
    def __init__(self, database_url: str, *, create_schema: bool = False) -> None:
        self.engine: Engine = create_engine(database_url, future=True)
        if create_schema:
            self._create_schema()

    def _create_schema(self) -> None:
        if self.engine.dialect.name == "postgresql":
            with self.engine.begin() as conn:
                conn.execute(text("SELECT pg_advisory_xact_lock(hashtext('civi_notification_schema'))"))
                metadata.create_all(conn)
            return

        metadata.create_all(self.engine)

    def queue_message(self, *, to: str, body: str, channel: str = "whatsapp") -> OutboxMessage:
        created_at = datetime.now(UTC).isoformat(timespec="seconds")
        with self.engine.begin() as conn:
            result = conn.execute(
                outbox.insert().values(
                    to=to,
                    body=body,
                    channel=channel,
                    status="queued",
                    created_at=created_at,
                    sent_at=None,
                )
            )
            message_id = int(result.inserted_primary_key[0])
        return OutboxMessage(
            id=message_id,
            to=to,
            body=body,
            channel=channel,
            status="queued",
            created_at=created_at,
            sent_at=None,
        )

    def list_queued(self, *, limit: int = 50) -> list[OutboxMessage]:
        stmt = (
            select(outbox)
            .where(outbox.c.status == "queued")
            .order_by(outbox.c.id)
            .limit(limit)
        )
        with self.engine.begin() as conn:
            rows = conn.execute(stmt).mappings().all()
        return [_outbox_from_row(row) for row in rows]

    def mark_sent(self, message_id: int) -> OutboxMessage | None:
        sent_at = datetime.now(UTC).isoformat(timespec="seconds")
        with self.engine.begin() as conn:
            row = conn.execute(select(outbox).where(outbox.c.id == message_id)).mappings().first()
            if row is None:
                return None
            conn.execute(
                update(outbox)
                .where(outbox.c.id == message_id)
                .values(status="sent", sent_at=sent_at)
            )
        message = _outbox_from_row(row)
        message.status = "sent"
        message.sent_at = sent_at
        return message

    def schedule_reminder(self, *, user_key: str, to: str, body: str, remind_at: str) -> Reminder:
        created_at = datetime.now(UTC).isoformat(timespec="seconds")
        with self.engine.begin() as conn:
            result = conn.execute(
                reminders.insert().values(
                    user_key=user_key,
                    to=to,
                    body=body,
                    remind_at=remind_at,
                    status="scheduled",
                    created_at=created_at,
                )
            )
            reminder_id = int(result.inserted_primary_key[0])
        return Reminder(
            id=reminder_id,
            user_key=user_key,
            to=to,
            body=body,
            remind_at=remind_at,
            status="scheduled",
            created_at=created_at,
        )

    def list_reminders(self, *, user_key: str | None = None) -> list[Reminder]:
        stmt = select(reminders).order_by(reminders.c.remind_at)
        if user_key:
            stmt = stmt.where(reminders.c.user_key == user_key)
        with self.engine.begin() as conn:
            rows = conn.execute(stmt).mappings().all()
        return [_reminder_from_row(row) for row in rows]

    def list_due_reminders(self, *, now: str, limit: int = 50) -> list[Reminder]:
        stmt = (
            select(reminders)
            .where(reminders.c.status == "scheduled")
            .where(reminders.c.remind_at <= now)
            .order_by(reminders.c.remind_at)
            .limit(limit)
        )
        with self.engine.begin() as conn:
            rows = conn.execute(stmt).mappings().all()
        return [_reminder_from_row(row) for row in rows]

    def queue_due_reminder(self, *, reminder_id: int) -> tuple[Reminder, OutboxMessage] | None:
        created_at = datetime.now(UTC).isoformat(timespec="seconds")
        with self.engine.begin() as conn:
            row = conn.execute(
                select(reminders)
                .where(reminders.c.id == reminder_id)
                .where(reminders.c.status == "scheduled")
            ).mappings().first()
            if row is None:
                return None
            updated = conn.execute(
                update(reminders)
                .where(reminders.c.id == reminder_id)
                .where(reminders.c.status == "scheduled")
                .values(status="queued")
            )
            if updated.rowcount != 1:
                return None
            result = conn.execute(
                outbox.insert().values(
                    to=row["to"],
                    body=row["body"],
                    channel="whatsapp",
                    status="queued",
                    created_at=created_at,
                    sent_at=None,
                )
            )
            message_id = int(result.inserted_primary_key[0])
        reminder = _reminder_from_row(row)
        reminder.status = "queued"
        message = OutboxMessage(
            id=message_id,
            to=str(row["to"]),
            body=str(row["body"]),
            channel="whatsapp",
            status="queued",
            created_at=created_at,
            sent_at=None,
        )
        return reminder, message


def _outbox_from_row(row) -> OutboxMessage:
    return OutboxMessage(
        id=int(row["id"]),
        to=str(row["to"]),
        body=str(row["body"]),
        channel=str(row["channel"]),
        status=str(row["status"]),
        created_at=str(row["created_at"]),
        sent_at=row["sent_at"],
    )


def _reminder_from_row(row) -> Reminder:
    return Reminder(
        id=int(row["id"]),
        user_key=str(row["user_key"]),
        to=str(row["to"]),
        body=str(row["body"]),
        remind_at=str(row["remind_at"]),
        status=str(row["status"]),
        created_at=str(row["created_at"]),
    )
