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


def test_manizales_parser_and_local_endpoint(monkeypatch: pytest.MonkeyPatch) -> None:
    from simit_service.adapters.outbound.manizales_provider import parse_manizales_text

    parsed = parse_manizales_text(
        """
        Estado de cuenta
        Comparendos: 1
        Multas: 1
        Total: $180.000
        """
    )
    assert parsed["tieneMultas"] is True
    assert parsed["resumen"]["total"] == 180000


def test_manizales_parser_detects_audiencia_row_with_zero_total() -> None:
    from simit_service.adapters.outbound.manizales_provider import parse_manizales_text

    parsed = parse_manizales_text(
        """
        Consulta de comparendos y multas
        QLX871
        D04 No detenerse ante luz roja o amarilla
        19/05/2026
        Audiencia
        No aplica
        Total multas ( 0 ) = COP 0
        """
    )
    assert parsed["tieneMultas"] is True
    assert parsed["resumen"]["total"] == 0
    assert parsed["detalles"]
    assert parsed["detalles"][0]["codigo"] == "D04"
    assert parsed["detalles"][0]["placa"] == "QLX871"
    assert "Audiencia" in str(parsed["detalles"][0].get("estado") or "")


def test_manizales_parser_joins_split_code_and_description() -> None:
    from simit_service.adapters.outbound.manizales_provider import parse_manizales_text

    parsed = parse_manizales_text(
        "Total multas ( 0 ) COP 0",
        details=[
            {
                "col_0": "Placa o documento\nQLX871\nDetalle fotodetección",
                "col_1": (
                    "Infracción\nD04 \n"
                    "No detenerse ante una luz roja o amarilla de semáf...\n"
                    "martes 19 de mayo 2026"
                ),
                "col_2": "Estado\nAudiencia",
                "col_3": "Valor multa\nNo aplica",
            }
        ],
    )
    assert parsed["tieneMultas"] is True
    assert parsed["detalles"][0]["codigo"] == "D04"
    assert "luz roja" in str(parsed["detalles"][0]["infraccion"]).lower()
    assert "19 de mayo" in str(parsed["detalles"][0]["fecha"]).lower()
    assert parsed["detalles"][0]["tipo"] == "fotodeteccion"


def test_manizales_parser_ignores_total_multas_zero_alone() -> None:
    from simit_service.adapters.outbound.manizales_provider import parse_manizales_text

    parsed = parse_manizales_text(
        """
        Estado de cuenta
        Total multas ( 0 ) = COP 0
        No se encontraron registros
        """
    )
    assert parsed["tieneMultas"] is False
    assert parsed["detalles"] == []


@pytest.mark.asyncio
async def test_manizales_endpoint_local_mode(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("INTERNAL_SERVICE_TOKEN", "test-token")
    monkeypatch.setenv("MANIZALES_PROVIDER_MODE", "local")
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        response = await client.post(
            "/internal/simit/multas/manizales",
            headers={"Authorization": "Bearer test-token"},
            json={"documento": "1234567890"},
        )
    assert response.status_code == 200
    body = response.json()
    assert body["success"] is True
    assert "tieneMultas" in body
    assert "resumen" in body
