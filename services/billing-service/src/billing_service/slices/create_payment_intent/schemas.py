from __future__ import annotations

from pydantic import BaseModel, Field


class CreatePaymentIntentRequest(BaseModel):
    user_key: str = Field(min_length=1, max_length=128)
    concept: str = Field(min_length=2, max_length=128)
    amount: int = Field(ge=0)
    currency: str = Field(default="COP", min_length=3, max_length=3)


class CreatePaymentIntentResponse(BaseModel):
    payment_intent_id: str
    status: str
    amount: int
    currency: str
    payment_url: str | None = None
