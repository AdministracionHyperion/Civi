from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException, status

from civi_common import require_internal_token

from .schemas import RuntVigenciaRequest, RuntVigenciaResponse
from .use_case import check_vigencia

router = APIRouter(prefix="/internal/runt", dependencies=[Depends(require_internal_token)])


@router.post("/vigencia", response_model=RuntVigenciaResponse)
async def post_vigencia(payload: RuntVigenciaRequest) -> RuntVigenciaResponse:
    try:
        return await check_vigencia(payload)
    except RuntimeError as exc:
        raise HTTPException(
            status_code=status.HTTP_502_BAD_GATEWAY,
            detail="RUNT provider is unavailable",
        ) from exc
