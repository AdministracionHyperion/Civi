from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException, status

from civi_common import require_internal_token

from .schemas import SimitMultasRequest, SimitMultasResponse
from .use_case import consult_multas

router = APIRouter(prefix="/internal/simit", dependencies=[Depends(require_internal_token)])


@router.post("/multas", response_model=SimitMultasResponse)
async def post_multas(payload: SimitMultasRequest) -> SimitMultasResponse:
    try:
        return await consult_multas(payload)
    except RuntimeError as exc:
        raise HTTPException(
            status_code=status.HTTP_502_BAD_GATEWAY,
            detail="SIMIT provider is unavailable",
        ) from exc
