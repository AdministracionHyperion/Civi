from __future__ import annotations

from dataclasses import dataclass, field
from datetime import UTC, datetime
from itertools import count
import os
from threading import Lock
from typing import Protocol


@dataclass
class OutboxMessage:
    id: int
    to: str
    body: str
    channel: str = "whatsapp"
    status: str = "queued"
    created_at: str = field(default_factory=lambda: datetime.now(UTC).isoformat(timespec="seconds"))
    sent_at: str | None = None


@dataclass
class Reminder:
    id: int
    user_key: str
    to: str
    body: str
    remind_at: str
    status: str = "scheduled"
    created_at: str = field(default_factory=lambda: datetime.now(UTC).isoformat(timespec="seconds"))


class NotificationRepository(Protocol):
    def queue_message(self, *, to: str, body: str, channel: str = "whatsapp") -> OutboxMessage:
        ...

    def list_queued(self, *, limit: int = 50) -> list[OutboxMessage]:
        ...

    def claim_queued_batch(self, *, limit: int = 50) -> list[OutboxMessage]:
        ...

    def mark_sent(self, message_id: int) -> OutboxMessage | None:
        ...

    def schedule_reminder(self, *, user_key: str, to: str, body: str, remind_at: str) -> Reminder:
        ...

    def list_reminders(self, *, user_key: str | None = None) -> list[Reminder]:
        ...

    def list_due_reminders(self, *, now: str, limit: int = 50) -> list[Reminder]:
        ...

    def queue_due_reminder(self, *, reminder_id: int) -> tuple[Reminder, OutboxMessage] | None:
        ...


class InMemoryNotificationRepository:
    def __init__(self) -> None:
        self._outbox: dict[int, OutboxMessage] = {}
        self._reminders: dict[int, Reminder] = {}
        self._outbox_ids = count(1)
        self._reminder_ids = count(1)
        self._lock = Lock()

    def queue_message(self, *, to: str, body: str, channel: str = "whatsapp") -> OutboxMessage:
        with self._lock:
            message = OutboxMessage(id=next(self._outbox_ids), to=to, body=body, channel=channel)
            self._outbox[message.id] = message
            return message

    def list_queued(self, *, limit: int = 50) -> list[OutboxMessage]:
        return [
            msg for msg in sorted(self._outbox.values(), key=lambda item: item.id)
            if msg.status == "queued"
        ][:limit]

    def claim_queued_batch(self, *, limit: int = 50) -> list[OutboxMessage]:
        with self._lock:
            batch = []
            for msg in sorted(self._outbox.values(), key=lambda item: item.id):
                if msg.status == "queued":
                    msg.status = "sending"
                    batch.append(msg)
                    if len(batch) >= limit:
                        break
            return batch

    def mark_sent(self, message_id: int) -> OutboxMessage | None:
        with self._lock:
            message = self._outbox.get(message_id)
            if not message:
                return None
            message.status = "sent"
            message.sent_at = datetime.now(UTC).isoformat(timespec="seconds")
            return message

    def schedule_reminder(self, *, user_key: str, to: str, body: str, remind_at: str) -> Reminder:
        with self._lock:
            reminder = Reminder(
                id=next(self._reminder_ids),
                user_key=user_key,
                to=to,
                body=body,
                remind_at=remind_at,
            )
            self._reminders[reminder.id] = reminder
            return reminder

    def list_reminders(self, *, user_key: str | None = None) -> list[Reminder]:
        reminders = sorted(self._reminders.values(), key=lambda item: item.remind_at)
        if user_key:
            reminders = [reminder for reminder in reminders if reminder.user_key == user_key]
        return reminders

    def list_due_reminders(self, *, now: str, limit: int = 50) -> list[Reminder]:
        return [
            reminder
            for reminder in sorted(self._reminders.values(), key=lambda item: item.remind_at)
            if reminder.status == "scheduled" and reminder.remind_at <= now
        ][:limit]

    def queue_due_reminder(self, *, reminder_id: int) -> tuple[Reminder, OutboxMessage] | None:
        with self._lock:
            reminder = self._reminders.get(reminder_id)
            if reminder is None or reminder.status != "scheduled":
                return None
            message = OutboxMessage(
                id=next(self._outbox_ids),
                to=reminder.to,
                body=reminder.body,
                channel="whatsapp",
            )
            self._outbox[message.id] = message
            reminder.status = "queued"
            return reminder, message


def repository_from_env() -> NotificationRepository:
    mode = os.getenv("NOTIFICATION_REPOSITORY_MODE", "memory").strip().lower()
    if mode in {"", "memory"}:
        return InMemoryNotificationRepository()
    if mode == "sql":
        database_url = os.getenv("NOTIFICATION_DATABASE_URL", "").strip()
        if not database_url:
            raise RuntimeError("NOTIFICATION_DATABASE_URL is required when NOTIFICATION_REPOSITORY_MODE=sql")
        from notification_service.adapters.outbound.sql_repository import SqlNotificationRepository

        auto_create = os.getenv("NOTIFICATION_AUTO_CREATE_SCHEMA", "").strip().lower() in {"1", "true", "yes"}
        return SqlNotificationRepository(database_url, create_schema=auto_create)
    raise RuntimeError(f"unsupported notification repository mode: {mode}")


repository = repository_from_env()
