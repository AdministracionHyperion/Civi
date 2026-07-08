from __future__ import annotations

from fastapi import APIRouter, Depends

from civi_common import require_internal_token

from .schemas import RunTurnRequest, RunTurnResponse
from .use_case import run_turn

router = APIRouter(tags=["conversation"])


@router.post(
    "/internal/conversations/turns",
    response_model=RunTurnResponse,
    dependencies=[Depends(require_internal_token)],
)
async def post_turn(payload: RunTurnRequest) -> RunTurnResponse:
    return await run_turn(payload)
