from __future__ import annotations

from typing import Protocol

from civi_common.events import EventPublisher, event_publisher_from_env
from appointment_service.adapters.outbound.notification_client import NotificationClient
from appointment_service.shared.mappers import appointment_to_dict
from appointment_service.shared.reminders import client_lead_minutes, compute_remind_at, partner_lead_minutes
from appointment_service.shared.repository import AppointmentRecord, repository

from .schemas import ConfirmAppointmentResponse


class NotificationPort(Protocol):
    async def send_whatsapp_message(self, *, to: str, body: str) -> dict[str, object]:
        ...

    async def schedule_reminder(
        self,
        *,
        user_key: str,
        to: str,
        body: str,
        remind_at: str,
    ) -> dict[str, object]:
        ...


async def confirm_appointment(
    *,
    appointment_id: int,
    notification_client: NotificationPort | None = None,
    event_publisher: EventPublisher | None = None,
) -> ConfirmAppointmentResponse:
    record = repository.confirm(appointment_id=appointment_id)
    if record is None:
        existing = repository.get(appointment_id=appointment_id)
        if existing is None:
            return ConfirmAppointmentResponse(success=False, error="not_found")
        return ConfirmAppointmentResponse(
            success=False,
            appointment=appointment_to_dict(existing),
            error="not_pending",
        )

    await (event_publisher or event_publisher_from_env()).publish(
        "appointment.confirmed",
        {
            "appointment_id": record.id,
            "user_key": record.user_key,
            "procedure": record.procedure,
            "starts_at": record.starts_at,
            "status": record.status,
        },
        producer="appointment-service",
    )

    client = notification_client or NotificationClient()
    notifications = await _notify_and_schedule(record, client=client)
    return ConfirmAppointmentResponse(
        appointment=appointment_to_dict(record),
        notifications=notifications,
    )


async def _notify_and_schedule(
    record: AppointmentRecord,
    *,
    client: NotificationPort,
) -> dict[str, object]:
    result: dict[str, object] = {}
    client_to = record.client_notification_to
    partner_to = record.partner_notification_to

    if client_to:
        try:
            await client.send_whatsapp_message(
                to=client_to,
                body=(
                    f"Tu cita #{record.id} de {record.procedure} en {record.place_name} "
                    f"({record.place_city}) para {record.starts_at} fue *confirmada* por el centro. "
                    "Te enviare un recordatorio antes."
                ),
            )
            result["client_notify"] = {"status": "sent", "to": client_to}
        except Exception as exc:
            result["client_notify"] = {"status": "failed", "reason": str(exc)}

        try:
            response = await client.schedule_reminder(
                user_key=record.user_key,
                to=client_to,
                body=(
                    f"Recordatorio Civi: cita de {record.procedure} en "
                    f"{record.place_name}, {record.place_city}, {record.starts_at}."
                ),
                remind_at=compute_remind_at(record.starts_at, lead_minutes=client_lead_minutes()),
            )
            reminder = response.get("reminder", {}) if isinstance(response, dict) else {}
            result["client_reminder"] = {
                "status": "scheduled",
                "reminder_id": reminder.get("id"),
                "to_tail": reminder.get("to_tail"),
            }
        except Exception as exc:
            result["client_reminder"] = {"status": "failed", "reason": str(exc)}
    else:
        result["client_notify"] = {"status": "skipped", "reason": "client_notification_to missing"}
        result["client_reminder"] = {"status": "skipped", "reason": "client_notification_to missing"}

    if partner_to:
        try:
            response = await client.schedule_reminder(
                user_key=f"partner:{record.place_id}",
                to=partner_to,
                body=(
                    f"Recordatorio Civi negocio: cita #{record.id} de {record.procedure} "
                    f"en {record.place_name} a las {record.starts_at}."
                ),
                remind_at=compute_remind_at(record.starts_at, lead_minutes=partner_lead_minutes()),
            )
            reminder = response.get("reminder", {}) if isinstance(response, dict) else {}
            result["partner_reminder"] = {
                "status": "scheduled",
                "reminder_id": reminder.get("id"),
                "to_tail": reminder.get("to_tail"),
            }
        except Exception as exc:
            result["partner_reminder"] = {"status": "failed", "reason": str(exc)}
    else:
        result["partner_reminder"] = {"status": "skipped", "reason": "partner_notification_to missing"}

    return result
