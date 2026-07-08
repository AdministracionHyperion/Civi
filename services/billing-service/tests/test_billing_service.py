from __future__ import annotations

import pytest
from httpx import ASGITransport, AsyncClient

from billing_service.main import app


@pytest.mark.asyncio
async def test_billing_service_creates_payment_intent_without_provider(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("INTERNAL_SERVICE_TOKEN", "test-token")
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        response = await client.post(
            "/internal/billing/payment-intents",
            headers={"Authorization": "Bearer test-token"},
            json={"user_key": "u1", "concept": "soat", "amount": 1000},
        )
    assert response.status_code == 200
    assert response.json()["status"] == "created_without_provider"
