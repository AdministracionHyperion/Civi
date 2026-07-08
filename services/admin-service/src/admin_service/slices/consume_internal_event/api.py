from __future__ import annotations

from fastapi import APIRouter, Depends

from civi_common import require_internal_token

from .schemas import ConsumeInternalEventRequest, ConsumeInternalEventResponse
from .use_case import consume_internal_event

router = APIRouter(tags=["admin"])


@router.post(
    "/internal/admin/events",
    response_model=ConsumeInternalEventResponse,
    dependencies=[Depends(require_internal_token)],
)
async def post_internal_event(payload: ConsumeInternalEventRequest) -> ConsumeInternalEventResponse:
    return await consume_internal_event(payload)
