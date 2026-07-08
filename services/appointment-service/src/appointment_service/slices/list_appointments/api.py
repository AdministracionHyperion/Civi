from __future__ import annotations

from fastapi import APIRouter, Depends, Query

from civi_common import require_internal_token

from .schemas import ListAppointmentsResponse
from .use_case import list_appointments

router = APIRouter(tags=["appointments"])


@router.get(
    "/internal/appointments",
    response_model=ListAppointmentsResponse,
    dependencies=[Depends(require_internal_token)],
)
async def get_appointments(user_key: str = Query(min_length=1)) -> ListAppointmentsResponse:
    return await list_appointments(user_key=user_key)
