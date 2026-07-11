from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException, status

from civi_common import require_internal_token

from .schemas import RuntPersonaRequest, RuntPersonaResponse
from .use_case import consult_persona

router = APIRouter(prefix="/internal/runt", dependencies=[Depends(require_internal_token)])


@router.post("/persona", response_model=RuntPersonaResponse)
async def post_persona(payload: RuntPersonaRequest) -> RuntPersonaResponse:
    try:
        return await consult_persona(payload)
    except Exception as exc:
        raise HTTPException(
            status_code=status.HTTP_502_BAD_GATEWAY,
            detail="RUNT persona provider is unavailable",
        ) from exc
