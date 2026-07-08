from __future__ import annotations

import json

import pytest
import httpx
from httpx import ASGITransport, AsyncClient

from runt_service.adapters.outbound.browser_provider import extract_info_general, parse_rtm_text, parse_soat_text
from runt_service.adapters.outbound.http_provider import HttpRuntProvider
from runt_service.adapters.outbound.persona_http_provider import HttpRuntPersonaProvider
from runt_service.main import app
from runt_service.shared.vehicle_analysis import build_vehicle_payload
from runt_service.slices.consult_persona.schemas import RuntPersonaRequest
from runt_service.slices.check_vigencia.schemas import RuntVigenciaRequest


@pytest.mark.asyncio
async def test_runt_health_and_vigencia(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("INTERNAL_SERVICE_TOKEN", "test-token")
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        health = await client.get("/health/live")
        assert health.status_code == 200
        response = await client.post(
            "/internal/runt/vigencia",
            headers={"Authorization": "Bearer test-token"},
            json={"placa": "abc123", "documento": "123456", "tipoDocumento": "CC"},
        )
        persona = await client.post(
            "/internal/runt/persona",
            headers={"Authorization": "Bearer test-token"},
            json={"documento": "123456"},
        )
    assert response.status_code == 200
    payload = response.json()
    assert payload["placa"] == "ABC123"
    assert payload["success"] is True
    assert payload["soat"]["vigente"] is True

    assert persona.status_code == 200
    assert persona.json()["ok"] is False
    assert persona.json()["error"] == "persona_provider_not_configured"


@pytest.mark.asyncio
async def test_runt_http_provider_normalizes_external_payload() -> None:
    async def handler(request: httpx.Request) -> httpx.Response:
        body = json.loads(request.content.decode("utf-8"))
        assert body == {
            "placa": "ABC123",
            "documento": "123456",
            "tipoDocumento": "CC",
            "forzarActualizacion": False,
        }
        return httpx.Response(
            200,
            json={
                "success": True,
                "placa": "ABC123",
                "fromCache": True,
                "vehiculo": {"marca": "Mazda", "linea": "2", "modelo": "2020"},
                "soat": {"vigente": True, "fechaVencimiento": "2026-12-31"},
                "rtm": {"vigente": True, "fechaVencimiento": "2026-11-30"},
                "alertas": [{"tipo": "SOAT", "nivel": "info"}],
            },
        )

    provider = HttpRuntProvider(
        api_url="https://provider.example.test/api/consultar",
        max_attempts=1,
        transport=httpx.MockTransport(handler),
    )
    result = await provider.check_vigencia(
        RuntVigenciaRequest(placa="abc123", documento="123456", tipoDocumento="CC")
    )

    assert result.placa == "ABC123"
    assert result.fromCache is True
    assert result.vehiculo["marca"] == "Mazda"
    assert result.soat["fechaVencimiento"] == "2026-12-31"
    assert result.alertas == [{"tipo": "SOAT", "nivel": "info"}]


def test_runt_browser_parsers_build_vehicle_payload() -> None:
    body_text = """
    Fecha de Matricula Inicial(dd/mm/aaaa):
    18/02/2022
    Clase de vehiculo:
    MOTOCICLETA
    Marca:
    HONDA
    Modelo:
    2022
    Linea:
    CB 125
    Color:
    NEGRO
    Estado:
    ACTIVO
    Tipo de servicio:
    PARTICULAR
    """
    soat_text = """
    Poliza SOAT
    01/01/2026
    02/01/2026
    02/01/2027
    VIGENTE
    AXA COLPATRIA
    987654321
    """
    rtm_text = """
    Certificado de revision tecnico mecanica y emisiones
    Fecha expedicion 01/02/2026
    Fecha vencimiento 01/02/2027
    Vigente
    SI
    """

    info = extract_info_general(body_text)
    payload = build_vehicle_payload(
        placa="ABC123",
        info_general=info,
        soat_data=parse_soat_text(soat_text),
        rtm_data=parse_rtm_text(rtm_text),
    )

    assert payload["vehiculo"]["marca"] == "HONDA"
    assert payload["soat"]["vigente"] is True
    assert payload["soat"]["fechaVencimiento"] == "02/01/2027"
    assert payload["rtm"]["tieneRTMVigente"] is True
    assert payload["rtm"]["proximaFechaRTM"] == "01/02/2027"


@pytest.mark.asyncio
async def test_runt_persona_http_provider_normalizes_payload() -> None:
    async def handler(request: httpx.Request) -> httpx.Response:
        body = json.loads(request.content.decode("utf-8"))
        assert body == {"documento": "123456"}
        return httpx.Response(
            200,
            json={
                "success": True,
                "nombre": "Persona Demo",
                "licencias": [{"categoria": "B1", "estado": "VIGENTE"}],
            },
        )

    provider = HttpRuntPersonaProvider(
        api_url="https://provider.example.test/api/consultar-persona",
        max_attempts=1,
        transport=httpx.MockTransport(handler),
    )
    result = await provider.consult_persona(RuntPersonaRequest(documento="123.456"))

    assert result.ok is True
    assert result.documentoTail == "3456"
    assert result.data is not None
    assert result.data["licencias"][0]["categoria"] == "B1"
