from __future__ import annotations

from fastapi import APIRouter, Depends

from civi_common import require_internal_token

from .schemas import CheckVigenciaRequest, CheckVigenciaResponse
from .use_case import check_vigencia

router = APIRouter(tags=["vehicle"])


@router.post(
    "/internal/vehicles/vigencia",
    response_model=CheckVigenciaResponse,
    dependencies=[Depends(require_internal_token)],
)
async def post_vigencia(payload: CheckVigenciaRequest) -> CheckVigenciaResponse:
    return await check_vigencia(payload)
