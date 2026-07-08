from __future__ import annotations

from fastapi import APIRouter, Depends

from civi_common import require_internal_token

from .schemas import GetCityInfoRequest, GetCityInfoResponse
from .use_case import get_city_info

router = APIRouter(prefix="/internal/knowledge", dependencies=[Depends(require_internal_token)])


@router.post("/city", response_model=GetCityInfoResponse)
async def post_city_info(payload: GetCityInfoRequest) -> GetCityInfoResponse:
    return await get_city_info(payload)
