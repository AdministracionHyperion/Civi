from __future__ import annotations

from fastapi import APIRouter, Depends

from civi_common import require_internal_token

from .schemas import ConsultMultasRequest, ConsultMultasResponse
from .use_case import consult_multas

router = APIRouter(tags=["vehicle"])


@router.post(
    "/internal/vehicles/multas",
    response_model=ConsultMultasResponse,
    dependencies=[Depends(require_internal_token)],
)
async def post_multas(payload: ConsultMultasRequest) -> ConsultMultasResponse:
    return await consult_multas(payload)
