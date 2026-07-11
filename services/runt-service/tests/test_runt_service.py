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
    monkeypatch.setenv("RUNT_PERSONA_PROVIDER_MODE", "local")
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
    persona_payload = persona.json()
    assert persona_payload["ok"] is True
    assert persona_payload["documentoTail"] == "3456"
    assert persona_payload["data"]["licencias"][0]["categorias"][0]["categoria"] == "A2"


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


def test_runt_persona_parsers_extract_licencias_and_categorias() -> None:
    from runt_service.adapters.outbound.persona_browser_provider import (
        parse_categorias_detalle,
        parse_licencias_from_text,
        parse_persona_ficha,
    )

    ficha_text = """
    Consulta Ciudadano
    Nombre completo:
    GABRIEL MATIAS RODRIGUEZ CASTRO
    Estado de la persona:
    ACTIVA
    Estado del conductor:
    ACTIVO
    Numero de inscripcion:
    24427916
    """
    # Portal often renders one cell per line.
    licenses_text = """
    Nro licencia
    OT Expide Lic.
    Fecha expedicion
    Estado
    1052838811
    DIR TTOyTTE FLORIDABLANCA
    30/06/2026
    ACTIVA
    Ver Detalle
    1052838811
    DIR TTOyTTE FLORIDABLANCA
    29/11/2024
    INACTIVA
    Ver Detalle
    """
    categorias_text = """
    Categorias de la licencia Nro: 1052838811
    Categoria Fecha expedicion Fecha vencimiento
    A2
    30/06/2026
    30/06/2036
    B1
    29/11/2024
    29/11/2034
    """

    ficha = parse_persona_ficha(ficha_text)
    licenses = parse_licencias_from_text(licenses_text)
    categorias = parse_categorias_detalle(categorias_text)

    assert ficha["nombre"] == "GABRIEL MATIAS RODRIGUEZ CASTRO"
    assert ficha["estadoPersona"] == "ACTIVA"
    assert ficha["estadoConductor"] == "ACTIVO"
    assert licenses[0]["numero"] == "1052838811"
    assert licenses[0]["estado"] == "ACTIVA"
    assert "FLORIDABLANCA" in (licenses[0]["ot"] or "")
    assert licenses[1]["estado"] == "INACTIVA"
    assert categorias == [
        {"categoria": "A2", "fechaExpedicion": "30/06/2026", "fechaVencimiento": "30/06/2036"},
        {"categoria": "B1", "fechaExpedicion": "29/11/2024", "fechaVencimiento": "29/11/2034"},
    ]


@pytest.mark.asyncio
async def test_runt_persona_browser_mode_uses_provider(monkeypatch: pytest.MonkeyPatch) -> None:
    from runt_service.slices.consult_persona import use_case as persona_use_case
    from runt_service.slices.consult_persona.schemas import RuntPersonaResponse

    class FakeBrowser:
        async def consult_persona(self, payload: RuntPersonaRequest) -> RuntPersonaResponse:
            return RuntPersonaResponse(
                ok=True,
                documentoTail=payload.documento[-4:],
                data={
                    "nombre": "Browser Demo",
                    "licencias": [
                        {
                            "numero": payload.documento,
                            "estado": "ACTIVA",
                            "categorias": [
                                {
                                    "categoria": "B1",
                                    "fechaExpedicion": "01/01/2020",
                                    "fechaVencimiento": "01/01/2030",
                                }
                            ],
                        }
                    ],
                },
                error=None,
                statusCode=200,
                checkedAt="2026-07-10T00:00:00+00:00",
            )

    monkeypatch.setenv("RUNT_PERSONA_PROVIDER_MODE", "browser")
    monkeypatch.setattr(
        persona_use_case.BrowserRuntPersonaProvider,
        "from_env",
        classmethod(lambda cls: FakeBrowser()),
    )

    result = await persona_use_case.consult_persona(RuntPersonaRequest(documento="1234567890"))
    assert result.ok is True
    assert result.data["nombre"] == "Browser Demo"
    assert result.data["licencias"][0]["categorias"][0]["fechaVencimiento"] == "01/01/2030"
