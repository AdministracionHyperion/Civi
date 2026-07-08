from __future__ import annotations

from fastapi import APIRouter, Depends

from civi_common import require_internal_token

from .schemas import CreatePaymentIntentRequest, CreatePaymentIntentResponse
from .use_case import create_payment_intent

router = APIRouter(prefix="/internal/billing", dependencies=[Depends(require_internal_token)])


@router.post("/payment-intents", response_model=CreatePaymentIntentResponse)
async def post_payment_intent(payload: CreatePaymentIntentRequest) -> CreatePaymentIntentResponse:
    return await create_payment_intent(payload)
