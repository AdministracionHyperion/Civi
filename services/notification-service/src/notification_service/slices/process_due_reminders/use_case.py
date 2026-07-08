from __future__ import annotations

from datetime import UTC, datetime

from civi_common.events import EventPublisher, event_publisher_from_env
from notification_service.shared.mappers import outbox_to_dict, reminder_to_dict
from notification_service.shared.repository import NotificationRepository, repository

from .schemas import ProcessDueRemindersResponse


async def process_due_reminders(
    *,
    now: str | None = None,
    limit: int = 50,
    notification_repository: NotificationRepository | None = None,
    event_publisher: EventPublisher | None = None,
) -> ProcessDueRemindersResponse:
    active_repository = notification_repository or repository
    active_now = now or datetime.now(UTC).isoformat(timespec="seconds")
    publisher = event_publisher or event_publisher_from_env()

    processed: list[dict[str, object]] = []
    for reminder in active_repository.list_due_reminders(now=active_now, limit=limit):
        queued = active_repository.queue_due_reminder(reminder_id=reminder.id)
        if queued is None:
            continue
        queued_reminder, message = queued
        reminder_payload = reminder_to_dict(queued_reminder)
        message_payload = outbox_to_dict(message)

        await publisher.publish(
            "reminder.due",
            {
                "reminder_id": queued_reminder.id,
                "user_key": queued_reminder.user_key,
            },
            producer="notification-service",
        )
        await publisher.publish(
            "notification.queued",
            {
                "message_id": message.id,
                "channel": message.channel,
                "to_tail": message_payload["to_tail"],
            },
            producer="notification-service",
        )
        processed.append({"reminder": reminder_payload, "message": message_payload})

    return ProcessDueRemindersResponse(processed=processed, count=len(processed))
