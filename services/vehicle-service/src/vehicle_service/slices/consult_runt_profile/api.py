from __future__ import annotations

from fastapi import APIRouter, Depends

from civi_common import require_internal_token

from .schemas import ConsultRuntProfileRequest, ConsultRuntProfileResponse
from .use_case import consult_runt_profile

router = APIRouter(prefix="/internal/vehicles", dependencies=[Depends(require_internal_token)])


@router.post("/runt-profile", response_model=ConsultRuntProfileResponse)
async def post_runt_profile(payload: ConsultRuntProfileRequest) -> ConsultRuntProfileResponse:
    return await consult_runt_profile(payload)
