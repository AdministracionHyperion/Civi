from __future__ import annotations

from civi_common.events import EventPublisher, event_publisher_from_env
from notification_service.shared.mappers import reminder_to_dict
from notification_service.shared.repository import repository

from .schemas import ScheduleReminderRequest, ScheduleReminderResponse


async def schedule_reminder(
    payload: ScheduleReminderRequest,
    *,
    event_publisher: EventPublisher | None = None,
) -> ScheduleReminderResponse:
    reminder = repository.schedule_reminder(
        user_key=payload.user_key,
        to=payload.to,
        body=payload.body,
        remind_at=payload.remind_at,
    )
    serialized = reminder_to_dict(reminder)
    await (event_publisher or event_publisher_from_env()).publish(
        "reminder.scheduled",
        {
            "reminder_id": reminder.id,
            "user_key": reminder.user_key,
            "to_tail": serialized["to_tail"],
            "remind_at": reminder.remind_at,
        },
        producer="notification-service",
    )
    return ScheduleReminderResponse(reminder=serialized)
