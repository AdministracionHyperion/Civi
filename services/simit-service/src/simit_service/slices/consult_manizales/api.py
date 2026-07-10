from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException, status

from civi_common import require_internal_token

from .schemas import ManizalesMultasRequest, ManizalesMultasResponse
from .use_case import consult_manizales_multas

router = APIRouter(prefix="/internal/simit", dependencies=[Depends(require_internal_token)])


@router.post("/multas/manizales", response_model=ManizalesMultasResponse)
async def post_manizales_multas(payload: ManizalesMultasRequest) -> ManizalesMultasResponse:
    try:
        return await consult_manizales_multas(payload)
    except RuntimeError as exc:
        raise HTTPException(
            status_code=status.HTTP_502_BAD_GATEWAY,
            detail="Manizales provider is unavailable",
        ) from exc
