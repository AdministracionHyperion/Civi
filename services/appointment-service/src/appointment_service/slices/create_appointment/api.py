from __future__ import annotations

from fastapi import APIRouter, Depends

from civi_common import require_internal_token

from .schemas import CreateAppointmentRequest, CreateAppointmentResponse
from .use_case import create_appointment

router = APIRouter(tags=["appointments"])


@router.post(
    "/internal/appointments",
    response_model=CreateAppointmentResponse,
    dependencies=[Depends(require_internal_token)],
    status_code=201,
)
async def post_appointment(payload: CreateAppointmentRequest) -> CreateAppointmentResponse:
    return await create_appointment(payload)
