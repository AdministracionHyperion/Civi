from __future__ import annotations

from fastapi import APIRouter, Depends

from civi_common import require_internal_token

from .schemas import GetInfraccionDetailRequest, GetInfraccionDetailResponse
from .use_case import get_infraccion_detail

router = APIRouter(prefix="/internal/quotes/infraccion", dependencies=[Depends(require_internal_token)])


@router.post("/detail", response_model=GetInfraccionDetailResponse)
async def post_infraccion_detail(payload: GetInfraccionDetailRequest) -> GetInfraccionDetailResponse:
    return await get_infraccion_detail(payload)
