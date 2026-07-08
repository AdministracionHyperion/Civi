from __future__ import annotations

from notification_service.shared.repository import OutboxMessage, Reminder


def outbox_to_dict(message: OutboxMessage) -> dict[str, object]:
    return {
        "id": message.id,
        "to_tail": _tail(message.to),
        "channel": message.channel,
        "body_length": len(message.body),
        "status": message.status,
        "created_at": message.created_at,
        "sent_at": message.sent_at,
    }


def reminder_to_dict(reminder: Reminder) -> dict[str, object]:
    return {
        "id": reminder.id,
        "user_key": reminder.user_key,
        "to_tail": _tail(reminder.to),
        "body_length": len(reminder.body),
        "remind_at": reminder.remind_at,
        "status": reminder.status,
        "created_at": reminder.created_at,
    }


def _tail(value: str) -> str:
    raw = str(value or "")
    return "****" if len(raw) <= 4 else f"****{raw[-4:]}"
