from __future__ import annotations

from datetime import UTC, datetime
from typing import Any, Protocol

from fastapi import HTTPException

from civi_common.events import EventPublisher, event_publisher_from_env
from appointment_service.adapters.outbound.notification_client import NotificationClient
from appointment_service.adapters.outbound.places_client import PlacesClient
from appointment_service.shared.mappers import appointment_to_dict
from appointment_service.shared.repository import repository

from .schemas import CreateAppointmentRequest, CreateAppointmentResponse


class NotificationPort(Protocol):
    async def send_whatsapp_message(self, *, to: str, body: str) -> dict[str, object]:
        ...


class PlacesPort(Protocol):
    async def get_ops_contact(self, site_id: str) -> dict[str, Any] | None:
        ...


async def create_appointment(
    payload: CreateAppointmentRequest,
    *,
    notification_client: NotificationPort | None = None,
    places_client: PlacesPort | None = None,
    event_publisher: EventPublisher | None = None,
) -> CreateAppointmentResponse:
    places = places_client or PlacesClient()
    ops = await places.get_ops_contact(payload.place.id)
    if ops is None or not ops.get("e164"):
        raise HTTPException(status_code=422, detail="place_not_notifiable")

    partner_to = str(ops["e164"])
    record = repository.create(
        user_key=payload.user_key,
        procedure=payload.procedure,
        place_id=payload.place.id,
        place_name=payload.place.name,
        place_address=payload.place.address,
        place_city=payload.place.city,
        starts_at=payload.starts_at,
        status="pending_partner",
        client_notification_to=payload.notification_to,
        partner_notification_to=partner_to,
    )

    await (event_publisher or event_publisher_from_env()).publish(
        "appointment.created",
        {
            "appointment_id": record.id,
            "user_key": record.user_key,
            "procedure": record.procedure,
            "starts_at": record.starts_at,
            "status": record.status,
            "place": {
                "id": record.place_id,
                "name": record.place_name,
                "city": record.place_city,
            },
        },
        producer="appointment-service",
    )

    notification = await _notify_partner(
        record_id=record.id,
        procedure=record.procedure,
        starts_at=record.starts_at,
        place_name=record.place_name,
        place_city=record.place_city,
        partner_to=partner_to,
        notification_client=notification_client,
    )
    if notification.get("status") == "sent":
        notified_at = datetime.now(UTC).isoformat(timespec="seconds")
        updated = repository.mark_partner_notified(appointment_id=record.id, notified_at=notified_at)
        if updated is not None:
            record = updated

    return CreateAppointmentResponse(
        appointment=appointment_to_dict(record),
        notification=notification,
    )


async def _notify_partner(
    *,
    record_id: int,
    procedure: str,
    starts_at: str,
    place_name: str,
    place_city: str,
    partner_to: str,
    notification_client: NotificationPort | None = None,
) -> dict[str, object]:
    body = (
        f"Nueva solicitud Civi #{record_id}\n"
        f"Tramite: {procedure}\n"
        f"Centro: {place_name} ({place_city})\n"
        f"Fecha: {starts_at}\n\n"
        f"Responde:\nCONFIRMAR {record_id}\no\nRECHAZAR {record_id}"
    )
    client = notification_client
    try:
        client = client or NotificationClient()
        await client.send_whatsapp_message(to=partner_to, body=body)
    except Exception as exc:
        return {"status": "failed", "reason": str(exc), "to": partner_to}
    return {"status": "sent", "to": partner_to, "kind": "partner_request"}
