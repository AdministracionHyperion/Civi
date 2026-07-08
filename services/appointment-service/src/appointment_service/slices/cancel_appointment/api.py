from __future__ import annotations

from fastapi import APIRouter, Depends, Query

from civi_common import require_internal_token

from .schemas import CancelAppointmentResponse
from .use_case import cancel_appointment

router = APIRouter(tags=["appointments"])


@router.delete(
    "/internal/appointments/{appointment_id}",
    response_model=CancelAppointmentResponse,
    dependencies=[Depends(require_internal_token)],
)
async def delete_appointment(
    appointment_id: int,
    user_key: str = Query(min_length=1),
) -> CancelAppointmentResponse:
    return await cancel_appointment(user_key=user_key, appointment_id=appointment_id)
