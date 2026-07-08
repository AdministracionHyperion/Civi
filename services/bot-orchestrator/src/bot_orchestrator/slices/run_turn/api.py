from __future__ import annotations

from fastapi import APIRouter, Depends

from civi_common import require_internal_token

from .schemas import AgentTurnRequest, AgentTurnResponse
from .use_case import run_agent_turn

router = APIRouter(tags=["agent"])


@router.post(
    "/internal/agent/turns",
    response_model=AgentTurnResponse,
    dependencies=[Depends(require_internal_token)],
)
async def post_agent_turn(payload: AgentTurnRequest) -> AgentTurnResponse:
    return await run_agent_turn(payload)
