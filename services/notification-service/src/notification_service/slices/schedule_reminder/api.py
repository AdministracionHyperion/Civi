from __future__ import annotations

from fastapi import APIRouter, Depends

from civi_common import require_internal_token

from .schemas import ScheduleReminderRequest, ScheduleReminderResponse
from .use_case import schedule_reminder

router = APIRouter(tags=["notifications"])


@router.post(
    "/internal/notifications/reminders",
    response_model=ScheduleReminderResponse,
    dependencies=[Depends(require_internal_token)],
    status_code=201,
)
async def post_reminder(payload: ScheduleReminderRequest) -> ScheduleReminderResponse:
    return await schedule_reminder(payload)
