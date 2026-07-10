from __future__ import annotations

from typing import Protocol

from fastapi import HTTPException

from civi_common.events import EventPublisher, event_publisher_from_env
from appointment_service.adapters.outbound.notification_client import NotificationClient
from appointment_service.adapters.outbound.places_client import PlacesCatalogUnavailable, PlacesClient
from appointment_service.shared.mappers import appointment_to_dict
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


class PlacesEligibilityClient(Protocol):
    async def booking_eligibility(self, site_id: str) -> dict[str, object]:
        ...


async def create_appointment(
    payload: CreateAppointmentRequest,
    *,
    notification_client: ReminderClient | None = None,
    event_publisher: EventPublisher | None = None,
    places_client: PlacesEligibilityClient | None = None,
) -> CreateAppointmentResponse:
    try:
        eligibility = await (places_client or PlacesClient()).booking_eligibility(payload.place.id)
    except PlacesCatalogUnavailable:
        raise HTTPException(status_code=503, detail="places_catalog_unavailable") from None
    if not eligibility.get("exists"):
        raise HTTPException(status_code=404, detail="place_not_found")
    eligible = eligibility.get("eligible_for_civi_booking")
    if eligible is None:
        eligible = bool(eligibility.get("is_bookable")) and eligibility.get("booking_mode") == "civi"
    if not eligible:
        reason = str(eligibility.get("eligibility_reason") or "place_not_bookable")
        raise HTTPException(status_code=422, detail=reason)

    place_name = str(eligibility.get("canonical_name") or payload.place.name)
    place_address = str(eligibility.get("canonical_address") or payload.place.address)
    place_city = str(eligibility.get("canonical_city") or payload.place.city)

    record = repository.create(
        user_key=payload.user_key,
        procedure=payload.procedure,
        place_id=payload.place.id,
        place_name=place_name,
        place_address=place_address,
        place_city=place_city,
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
    # Use canonical place fields for reminder text
    reminder_payload = payload.model_copy(
        update={"place": payload.place.model_copy(update={"name": place_name, "address": place_address, "city": place_city})}
    )
    notification = await _schedule_reminder(reminder_payload, notification_client=notification_client)
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
            remind_at=payload.starts_at,
        )
    except Exception as exc:
        return {"status": "failed", "reason": str(exc)}

    reminder = response.get("reminder", {}) if isinstance(response, dict) else {}
    return {
        "status": "scheduled",
        "reminder_id": reminder.get("id"),
        "to_tail": reminder.get("to_tail"),
    }
