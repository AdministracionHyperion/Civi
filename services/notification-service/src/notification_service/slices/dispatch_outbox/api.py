from __future__ import annotations

from fastapi import APIRouter, Depends, Query

from civi_common import require_internal_token

from .schemas import DispatchOutboxResponse
from .use_case import dispatch_outbox

router = APIRouter(tags=["notifications"])


@router.post(
    "/internal/notifications/outbox/dispatch",
    response_model=DispatchOutboxResponse,
    dependencies=[Depends(require_internal_token)],
)
async def post_dispatch(limit: int = Query(default=50, ge=1, le=500)) -> DispatchOutboxResponse:
    return await dispatch_outbox(limit=limit)
