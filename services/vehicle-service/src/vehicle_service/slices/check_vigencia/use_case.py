from __future__ import annotations

from typing import Protocol

from vehicle_service.adapters.outbound.runt_client import RuntClient
from vehicle_service.shared.cache_repository import VehicleCacheRepository, repository

from .schemas import CheckVigenciaRequest, CheckVigenciaResponse


class VigenciaClient(Protocol):
    async def consultar_vigencia(
        self,
        *,
        placa: str,
        documento: str,
        tipo_documento: str = "CC",
        forzar_actualizacion: bool = False,
    ) -> dict[str, object]:
        ...


async def check_vigencia(
    payload: CheckVigenciaRequest,
    *,
    runt_client: VigenciaClient | None = None,
    cache_repository: VehicleCacheRepository | None = None,
) -> CheckVigenciaResponse:
    active_cache = cache_repository or repository
    if not payload.forzar_actualizacion:
        cached = active_cache.get_vigencia(
            placa=payload.placa,
            documento=payload.documento,
            tipo_documento=payload.tipo_documento,
        )
        if cached is not None:
            cached_payload = dict(cached.payload)
            cached_payload["fromCache"] = True
            return CheckVigenciaResponse.model_validate(cached_payload)

    client = runt_client or RuntClient()
    data = await client.consultar_vigencia(
        placa=payload.placa,
        documento=payload.documento,
        tipo_documento=payload.tipo_documento,
        forzar_actualizacion=payload.forzar_actualizacion,
    )
    fresh_payload = dict(data)
    fresh_payload["fromCache"] = False
    active_cache.save_vigencia(
        placa=payload.placa,
        documento=payload.documento,
        tipo_documento=payload.tipo_documento,
        payload=fresh_payload,
    )
    return CheckVigenciaResponse.model_validate(fresh_payload)
