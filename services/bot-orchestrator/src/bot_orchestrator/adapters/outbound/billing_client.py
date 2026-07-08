from __future__ import annotations

import os
from typing import Any

import httpx


class BillingClient:
    def __init__(self, *, base_url: str | None = None, token: str | None = None) -> None:
        self.base_url = (base_url or os.getenv("BILLING_SERVICE_URL", "http://localhost:8092")).rstrip("/")
        self.token = (token if token is not None else os.getenv("INTERNAL_SERVICE_TOKEN", "")).strip()
        if not self.token:
            raise RuntimeError("INTERNAL_SERVICE_TOKEN is required for billing service calls")

    @property
    def _headers(self) -> dict[str, str]:
        return {"Authorization": f"Bearer {self.token}"}

    async def create_payment_intent(
        self,
        *,
        user_key: str,
        concept: str,
        amount: int,
        currency: str = "COP",
    ) -> dict[str, Any]:
        async with httpx.AsyncClient(timeout=20.0) as client:
            response = await client.post(
                f"{self.base_url}/internal/billing/payment-intents",
                json={"user_key": user_key, "concept": concept, "amount": amount, "currency": currency},
                headers=self._headers,
            )
            response.raise_for_status()
            return response.json()
