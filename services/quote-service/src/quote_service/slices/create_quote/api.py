from __future__ import annotations

from fastapi import APIRouter, Depends

from civi_common import require_internal_token

from .schemas import CreateQuoteRequest, CreateQuoteResponse
from .use_case import create_quote

router = APIRouter(prefix="/internal/quotes", dependencies=[Depends(require_internal_token)])


@router.post("", response_model=CreateQuoteResponse)
async def post_quote(payload: CreateQuoteRequest) -> CreateQuoteResponse:
    return await create_quote(payload)
