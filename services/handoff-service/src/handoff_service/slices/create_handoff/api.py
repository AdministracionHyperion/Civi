from __future__ import annotations

from fastapi import APIRouter, Depends

from civi_common import require_internal_token

from .schemas import CreateHandoffRequest, CreateHandoffResponse
from .use_case import create_handoff

router = APIRouter(prefix="/internal/handoffs", dependencies=[Depends(require_internal_token)])


@router.post("", response_model=CreateHandoffResponse)
async def post_handoff(payload: CreateHandoffRequest) -> CreateHandoffResponse:
    return await create_handoff(payload)
