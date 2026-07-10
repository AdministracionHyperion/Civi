from __future__ import annotations

from fastapi import APIRouter, Depends

from civi_common import require_internal_token

from .schemas import ConfirmAppointmentResponse
from .use_case import confirm_appointment

router = APIRouter(tags=["appointments"])


@router.post(
    "/internal/appointments/{appointment_id}/confirm",
    response_model=ConfirmAppointmentResponse,
    dependencies=[Depends(require_internal_token)],
)
async def post_confirm_appointment(appointment_id: int) -> ConfirmAppointmentResponse:
    return await confirm_appointment(appointment_id=appointment_id)
