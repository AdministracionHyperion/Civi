from __future__ import annotations

from typing import Protocol

from civi_common.events import EventPublisher, event_publisher_from_env
from appointment_service.adapters.outbound.notification_client import NotificationClient
from appointment_service.shared.mappers import appointment_to_dict
from appointment_service.shared.reminders import compute_remind_at
from appointment_service.shared.repository import repository

from .schemas import CreateAppointmentRequest, CreateAppointmentResponse


class ReminderClient(Protocol):
    async def schedule_reminder(
        self,
        *,
        user_key: str,
        to: str,
        body: str,
        remind_at: str,
    ) -> dict[str, object]:
        ...


async def create_appointment(
    payload: CreateAppointmentRequest,
    *,
    notification_client: ReminderClient | None = None,
    event_publisher: EventPublisher | None = None,
) -> CreateAppointmentResponse:
    record = repository.create(
        user_key=payload.user_key,
        procedure=payload.procedure,
        place_id=payload.place.id,
        place_name=payload.place.name,
        place_address=payload.place.address,
        place_city=payload.place.city,
        starts_at=payload.starts_at,
    )
    await (event_publisher or event_publisher_from_env()).publish(
        "appointment.created",
        {
            "appointment_id": record.id,
            "user_key": record.user_key,
            "procedure": record.procedure,
            "starts_at": record.starts_at,
            "place": {
                "id": record.place_id,
                "name": record.place_name,
                "city": record.place_city,
            },
        },
        producer="appointment-service",
    )
    notification = await _schedule_reminder(payload, notification_client=notification_client)
    return CreateAppointmentResponse(appointment=appointment_to_dict(record), notification=notification)


async def _schedule_reminder(
    payload: CreateAppointmentRequest,
    *,
    notification_client: ReminderClient | None = None,
) -> dict[str, object]:
    if not payload.notification_to:
        return {"status": "skipped", "reason": "notification_to not provided"}

    client = notification_client
    try:
        client = client or NotificationClient()
        response = await client.schedule_reminder(
            user_key=payload.user_key,
            to=payload.notification_to,
            body=(
                f"Recordatorio Civi: cita de {payload.procedure} en "
                f"{payload.place.name}, {payload.place.city}, {payload.starts_at}."
            ),
            remind_at=compute_remind_at(payload.starts_at),
        )
    except Exception as exc:
        return {"status": "failed", "reason": str(exc)}

    reminder = response.get("reminder", {}) if isinstance(response, dict) else {}
    return {
        "status": "scheduled",
        "reminder_id": reminder.get("id"),
        "to_tail": reminder.get("to_tail"),
    }
