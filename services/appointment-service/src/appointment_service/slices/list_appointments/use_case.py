from __future__ import annotations

from appointment_service.shared.mappers import appointment_to_dict
from appointment_service.shared.repository import repository

from .schemas import ListAppointmentsResponse


async def list_appointments(*, user_key: str) -> ListAppointmentsResponse:
    return ListAppointmentsResponse(
        appointments=[
            appointment_to_dict(record)
            for record in repository.list_for_user(user_key=user_key)
        ]
    )
