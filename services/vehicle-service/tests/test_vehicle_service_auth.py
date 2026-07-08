from __future__ import annotations

import pytest
from fastapi.testclient import TestClient

from vehicle_service.adapters.outbound.sql_cache_repository import SqlVehicleCacheRepository
from vehicle_service.main import app
from vehicle_service.shared.cache_repository import InMemoryVehicleCacheRepository, document_tail
from vehicle_service.slices.check_vigencia.schemas import CheckVigenciaRequest
from vehicle_service.slices.check_vigencia.use_case import check_vigencia
from vehicle_service.slices.consult_multas.schemas import ConsultMultasRequest
from vehicle_service.slices.consult_multas.use_case import consult_multas
from vehicle_service.slices.consult_runt_profile.schemas import ConsultRuntProfileRequest
from vehicle_service.slices.consult_runt_profile.use_case import consult_runt_profile


class FakeRuntClient:
    def __init__(self) -> None:
        self.vigencia_calls = 0
        self.persona_calls = 0

    async def consultar_vigencia(
        self,
        *,
        placa: str,
        documento: str,
        tipo_documento: str = "CC",
        forzar_actualizacion: bool = False,
    ) -> dict[str, object]:
        self.vigencia_calls += 1
        return {
            "success": True,
            "placa": placa.upper(),
            "vehiculo": {"marca": "Mazda"},
            "soat": {"fechaVencimiento": "2026-10-15"},
            "rtm": {"fechaVencimiento": "2026-11-20"},
            "alertas": [],
        }

    async def consultar_persona(self, *, documento: str) -> dict[str, object]:
        self.persona_calls += 1
        return {
            "ok": True,
            "documentoTail": documento[-4:],
            "data": {"licencias": [{"categoria": "B1", "estado": "VIGENTE"}]},
            "error": None,
            "statusCode": 200,
            "checkedAt": "2026-07-07T00:00:00+00:00",
        }


class FakeSimitClient:
    def __init__(self) -> None:
        self.multas_calls = 0

    async def consultar_multas(self, *, documento: str) -> dict[str, object]:
        self.multas_calls += 1
        return {
            "success": True,
            "documentoTail": document_tail(documento),
            "tieneMultas": False,
            "resumen": {"total": 0},
            "detalles": [],
        }


def test_vehicle_internal_status_requires_token(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("INTERNAL_SERVICE_TOKEN", "internal-test-token")
    client = TestClient(app)

    assert client.get("/internal/status").status_code == 401

    response = client.get(
        "/internal/status",
        headers={"Authorization": "Bearer internal-test-token"},
    )
    assert response.status_code == 200
    assert response.json()["service"] == "vehicle-service"


@pytest.mark.asyncio
async def test_check_vigencia_uses_cache_after_first_runt_call() -> None:
    repo = InMemoryVehicleCacheRepository()
    runt = FakeRuntClient()
    payload = CheckVigenciaRequest(
        placa="abc123",
        documento="123456789",
        tipoDocumento="CC",
    )

    first = await check_vigencia(payload, runt_client=runt, cache_repository=repo)
    second = await check_vigencia(payload, runt_client=runt, cache_repository=repo)

    assert first.from_cache is False
    assert second.from_cache is True
    assert runt.vigencia_calls == 1


@pytest.mark.asyncio
async def test_check_vigencia_force_refresh_bypasses_cache() -> None:
    repo = InMemoryVehicleCacheRepository()
    runt = FakeRuntClient()

    await check_vigencia(
        CheckVigenciaRequest(placa="abc123", documento="123456789", tipoDocumento="CC"),
        runt_client=runt,
        cache_repository=repo,
    )
    refreshed = await check_vigencia(
        CheckVigenciaRequest(
            placa="abc123",
            documento="123456789",
            tipoDocumento="CC",
            forzarActualizacion=True,
        ),
        runt_client=runt,
        cache_repository=repo,
    )

    assert refreshed.from_cache is False
    assert runt.vigencia_calls == 2


@pytest.mark.asyncio
async def test_consult_multas_uses_cache_after_first_simit_call() -> None:
    repo = InMemoryVehicleCacheRepository()
    simit = FakeSimitClient()
    payload = ConsultMultasRequest(documento="123456789")

    first = await consult_multas(payload, simit_client=simit, cache_repository=repo)
    second = await consult_multas(payload, simit_client=simit, cache_repository=repo)

    assert first.tieneMultas is False
    assert second.tieneMultas is False
    assert simit.multas_calls == 1


@pytest.mark.asyncio
async def test_consult_runt_profile_uses_runt_client() -> None:
    runt = FakeRuntClient()
    result = await consult_runt_profile(
        ConsultRuntProfileRequest(documento="123456789"),
        runt_client=runt,
    )

    assert result.ok is True
    assert result.documentoTail == "6789"
    assert result.data == {"licencias": [{"categoria": "B1", "estado": "VIGENTE"}]}
    assert runt.persona_calls == 1


def test_sql_vehicle_cache_repository_persists_without_raw_document() -> None:
    repo = SqlVehicleCacheRepository("sqlite+pysqlite:///:memory:", create_schema=True)
    payload = {"success": True, "placa": "ABC123", "fromCache": False}

    repo.save_vigencia(
        placa="ABC123",
        documento="123456789",
        tipo_documento="CC",
        payload=payload,
    )
    record = repo.get_vigencia(placa="ABC123", documento="123456789", tipo_documento="CC")

    assert record is not None
    assert record.payload == payload
    assert "123456789" not in record.cache_key
