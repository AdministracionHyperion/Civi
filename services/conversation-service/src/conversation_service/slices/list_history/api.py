from __future__ import annotations

from fastapi import APIRouter, Depends, Query

from civi_common import require_internal_token

from .schemas import ListHistoryResponse
from .use_case import list_history

router = APIRouter(tags=["conversation"])


@router.get(
    "/internal/conversations/history",
    response_model=ListHistoryResponse,
    dependencies=[Depends(require_internal_token)],
)
async def get_history(
    user_key: str = Query(min_length=1),
    limit: int = Query(default=20, ge=1, le=100),
) -> ListHistoryResponse:
    return await list_history(user_key=user_key, limit=limit)
