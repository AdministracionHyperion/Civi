from __future__ import annotations

from civi_common.events import EventPublisher, event_publisher_from_env
from appointment_service.shared.mappers import appointment_to_dict
from appointment_service.shared.repository import repository

from .schemas import CancelAppointmentResponse


async def cancel_appointment(
    *,
    user_key: str,
    appointment_id: int,
    event_publisher: EventPublisher | None = None,
) -> CancelAppointmentResponse:
    record = repository.cancel(user_key=user_key, appointment_id=appointment_id)
    if record is None:
        return CancelAppointmentResponse(success=False, error="appointment not found or already cancelled")
    await (event_publisher or event_publisher_from_env()).publish(
        "appointment.cancelled",
        {
            "appointment_id": record.id,
            "user_key": record.user_key,
        },
        producer="appointment-service",
    )
    return CancelAppointmentResponse(success=True, appointment=appointment_to_dict(record))
