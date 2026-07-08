from __future__ import annotations

from fastapi import APIRouter, Depends

from civi_common import require_internal_token

from .schemas import GetDomainInfoRequest, GetDomainInfoResponse
from .use_case import get_domain_info

router = APIRouter(prefix="/internal/knowledge", dependencies=[Depends(require_internal_token)])


@router.post("/info", response_model=GetDomainInfoResponse)
async def post_domain_info(payload: GetDomainInfoRequest) -> GetDomainInfoResponse:
    return await get_domain_info(payload)
