from __future__ import annotations

import pytest
from httpx import ASGITransport, AsyncClient

from quote_service.main import app


@pytest.mark.asyncio
async def test_quote_service_creates_reference_quote(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("INTERNAL_SERVICE_TOKEN", "test-token")
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        response = await client.post(
            "/internal/quotes",
            headers={"Authorization": "Bearer test-token"},
            json={"service_type": "soat", "city": "Bogota"},
        )
    assert response.status_code == 200
    assert response.json()["currency"] == "COP"


@pytest.mark.asyncio
async def test_quote_service_creates_exact_soat_quote(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("INTERNAL_SERVICE_TOKEN", "test-token")
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        response = await client.post(
            "/internal/quotes",
            headers={"Authorization": "Bearer test-token"},
            json={"service_type": "soat", "vehicle_type": "moto", "cilindraje": 150, "modelo": 2020},
        )

    assert response.status_code == 200
    body = response.json()
    assert body["quote_type"] == "exact"
    assert body["price_cop"] == 343300
    assert body["price_min"] == body["price_max"] == 343300


@pytest.mark.asyncio
async def test_quote_service_quotes_infraction_by_text(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("INTERNAL_SERVICE_TOKEN", "test-token")
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        response = await client.post(
            "/internal/quotes",
            headers={"Authorization": "Bearer test-token"},
            json={"service_type": "infraccion", "consulta": "multa por semaforo en rojo"},
        )

    assert response.status_code == 200
    body = response.json()
    assert body["quote_type"] == "exact"
    assert body["service_type"] == "infraccion"
    assert body["price_cop"] > 0
    assert body["details"]["codigo"]
