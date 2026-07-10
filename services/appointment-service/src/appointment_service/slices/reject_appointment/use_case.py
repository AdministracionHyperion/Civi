from __future__ import annotations

from typing import Protocol

from civi_common.events import EventPublisher, event_publisher_from_env
from appointment_service.adapters.outbound.notification_client import NotificationClient
from appointment_service.shared.mappers import appointment_to_dict
from appointment_service.shared.repository import repository

from .schemas import RejectAppointmentResponse


class NotificationPort(Protocol):
    async def send_whatsapp_message(self, *, to: str, body: str) -> dict[str, object]:
        ...


async def reject_appointment(
    *,
    appointment_id: int,
    notification_client: NotificationPort | None = None,
    event_publisher: EventPublisher | None = None,
) -> RejectAppointmentResponse:
    record = repository.reject(appointment_id=appointment_id)
    if record is None:
        existing = repository.get(appointment_id=appointment_id)
        if existing is None:
            return RejectAppointmentResponse(success=False, error="not_found")
        return RejectAppointmentResponse(
            success=False,
            appointment=appointment_to_dict(existing),
            error="not_pending",
        )

    await (event_publisher or event_publisher_from_env()).publish(
        "appointment.rejected",
        {
            "appointment_id": record.id,
            "user_key": record.user_key,
            "procedure": record.procedure,
            "starts_at": record.starts_at,
            "status": record.status,
        },
        producer="appointment-service",
    )

    notifications: dict[str, object] = {}
    client_to = record.client_notification_to
    if client_to:
        client = notification_client or NotificationClient()
        try:
            await client.send_whatsapp_message(
                to=client_to,
                body=(
                    f"El centro no pudo confirmar tu cita #{record.id} de {record.procedure} "
                    f"en {record.place_name} para {record.starts_at}. "
                    "Si quieres, te ayudo a buscar otro centro afiliado Civi."
                ),
            )
            notifications["client_notify"] = {"status": "sent", "to": client_to}
        except Exception as exc:
            notifications["client_notify"] = {"status": "failed", "reason": str(exc)}
    else:
        notifications["client_notify"] = {"status": "skipped", "reason": "client_notification_to missing"}

    return RejectAppointmentResponse(
        appointment=appointment_to_dict(record),
        notifications=notifications,
    )
