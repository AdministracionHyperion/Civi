from __future__ import annotations

import hashlib

from .schemas import CreatePaymentIntentRequest, CreatePaymentIntentResponse


async def create_payment_intent(payload: CreatePaymentIntentRequest) -> CreatePaymentIntentResponse:
    digest = hashlib.sha256(f"{payload.user_key}:{payload.concept}:{payload.amount}".encode()).hexdigest()[:16]
    return CreatePaymentIntentResponse(
        payment_intent_id=f"pay_{digest}",
        status="created_without_provider",
        amount=payload.amount,
        currency=payload.currency.upper(),
    )
