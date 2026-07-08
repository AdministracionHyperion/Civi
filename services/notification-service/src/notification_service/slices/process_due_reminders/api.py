from __future__ import annotations

from fastapi import APIRouter, Depends, Query

from civi_common import require_internal_token

from .schemas import ProcessDueRemindersResponse
from .use_case import process_due_reminders

router = APIRouter(tags=["notifications"])


@router.post(
    "/internal/notifications/reminders/process-due",
    response_model=ProcessDueRemindersResponse,
    dependencies=[Depends(require_internal_token)],
)
async def post_process_due_reminders(
    now: str | None = Query(default=None, min_length=10),
    limit: int = Query(default=50, ge=1, le=500),
) -> ProcessDueRemindersResponse:
    return await process_due_reminders(now=now, limit=limit)
