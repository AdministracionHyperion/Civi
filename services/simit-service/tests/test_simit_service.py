from __future__ import annotations

import json

import pytest
import httpx
from httpx import ASGITransport, AsyncClient

from simit_service.adapters.outbound.browser_provider import parse_simit_text
from simit_service.adapters.outbound.http_provider import HttpSimitProvider
from simit_service.main import app
from simit_service.slices.consult_multas.schemas import SimitMultasRequest


@pytest.mark.asyncio
async def test_simit_health_and_multas(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("INTERNAL_SERVICE_TOKEN", "test-token")
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        health = await client.get("/health/live")
        assert health.status_code == 200
        response = await client.post(
            "/internal/simit/multas",
            headers={"Authorization": "Bearer test-token"},
            json={"documento": "123456"},
        )
    assert response.status_code == 200
    assert response.json()["success"] is True
    assert "resumen" in response.json()


@pytest.mark.asyncio
async def test_simit_http_provider_normalizes_external_payload() -> None:
    async def handler(request: httpx.Request) -> httpx.Response:
        body = json.loads(request.content.decode("utf-8"))
        assert body == {"documento": "123456"}
        return httpx.Response(
            200,
            json={
                "success": True,
                "documento": "123456",
                "multas": {
                    "tieneMultas": True,
                    "resumen": {"comparendos": "2", "multas": 1, "total": "$350.000"},
                    "mensaje": "Tiene obligaciones pendientes.",
                    "detalles": [{"numero": "ABC", "valor": "$350.000"}],
                },
            },
        )

    provider = HttpSimitProvider(
        api_url="https://provider.example.test/api/multas",
        max_attempts=1,
        transport=httpx.MockTransport(handler),
    )
    result = await provider.consult_multas(SimitMultasRequest(documento="123.456"))

    assert result.documentoTail == "3456"
    assert result.tieneMultas is True
    assert result.resumen == {"comparendos": 2, "multas": 1, "total": 350000}
    assert result.detalles == [{"numero": "ABC", "valor": "$350.000"}]


def test_simit_browser_parser_extracts_summary_and_details() -> None:
    parsed = parse_simit_text(
        """
        Resumen
        Comparendos: 2
        Multas: 1
        Acuerdos de pago: 0
        Total: $ 350.000
        """,
        details=[{"numero": "ABC", "valor": "$350.000"}],
    )

    assert parsed["tieneMultas"] is True
    assert parsed["resumen"] == {"comparendos": 2, "multas": 1, "acuerdosPago": 0, "total": 350000}
    assert parsed["detalles"] == [{"numero": "ABC", "valor": "$350.000"}]
