from __future__ import annotations

from fastapi import APIRouter, Depends

from civi_common import require_internal_token

from .schemas import FindNearestPlaceRequest, FindNearestPlaceResponse
from .use_case import find_nearest_place

router = APIRouter(tags=["places"])


@router.post(
    "/internal/places/nearest",
    response_model=FindNearestPlaceResponse,
    dependencies=[Depends(require_internal_token)],
)
async def post_nearest(payload: FindNearestPlaceRequest) -> FindNearestPlaceResponse:
    return await find_nearest_place(payload)
