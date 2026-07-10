from __future__ import annotations

from fastapi import APIRouter, Depends

from civi_common import require_internal_token

from .schemas import RejectAppointmentResponse
from .use_case import reject_appointment

router = APIRouter(tags=["appointments"])


@router.post(
    "/internal/appointments/{appointment_id}/reject",
    response_model=RejectAppointmentResponse,
    dependencies=[Depends(require_internal_token)],
)
async def post_reject_appointment(appointment_id: int) -> RejectAppointmentResponse:
    return await reject_appointment(appointment_id=appointment_id)
