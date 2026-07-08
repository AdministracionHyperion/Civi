from __future__ import annotations

import pytest

import bot_orchestrator.slices.run_turn.use_case as bot_turn
from bot_orchestrator.slices.run_turn.schemas import AgentTurnRequest


class FakeQuoteClient:
    async def create(self, **payload: object) -> dict[str, object]:
        service_type = str(payload["service_type"])
        return {
            "service_type": service_type,
            "price_min": 350000,
            "price_max": 1200000,
            "currency": "COP",
            "disclaimer": "Valor referencial.",
        }


class FakeBillingClient:
    async def create_payment_intent(
        self,
        *,
        user_key: str,
        concept: str,
        amount: int,
        currency: str = "COP",
    ) -> dict[str, object]:
        return {"payment_intent_id": "pay_test", "status": "created_without_provider", "amount": amount, "currency": currency}


class FakeHandoffClient:
    async def create(self, *, user_key: str, reason: str, channel: str) -> dict[str, object]:
        return {"handoff_id": "handoff_test", "status": "queued", "message": "Te paso con un asesor."}


@pytest.mark.asyncio
async def test_quote_question_uses_quote_tool(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(bot_turn, "QuoteClient", lambda: FakeQuoteClient())

    response = await bot_turn.run_agent_turn(AgentTurnRequest(user_key="u1", text="cuanto cuesta el SOAT"))

    assert response.mode == "quote_created"
    assert response.tool_calls == ["quote.create"]
    assert "350000" in response.text


@pytest.mark.asyncio
async def test_payment_question_uses_billing_tool(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(bot_turn, "BillingClient", lambda: FakeBillingClient())

    response = await bot_turn.run_agent_turn(AgentTurnRequest(user_key="u1", text="quiero pagar"))

    assert response.mode == "payment_intent_created"
    assert response.tool_calls == ["billing.payment_intent.create"]
    assert "proveedor de pagos" in response.text


@pytest.mark.asyncio
async def test_human_question_uses_handoff_tool(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(bot_turn, "HandoffClient", lambda: FakeHandoffClient())

    response = await bot_turn.run_agent_turn(AgentTurnRequest(user_key="u1", text="quiero hablar con un asesor"))

    assert response.mode == "handoff_queued"
    assert response.tool_calls == ["handoff.create"]
    assert "asesor" in response.text
