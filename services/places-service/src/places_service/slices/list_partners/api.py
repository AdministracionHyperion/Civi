from __future__ import annotations

from fastapi import APIRouter, Depends

from civi_common import require_internal_token

from .schemas import ListPartnersResponse
from .use_case import list_partners

router = APIRouter(tags=["places"])


@router.get(
    "/internal/places/partners",
    response_model=ListPartnersResponse,
    dependencies=[Depends(require_internal_token)],
)
async def get_partners() -> ListPartnersResponse:
    return await list_partners()
