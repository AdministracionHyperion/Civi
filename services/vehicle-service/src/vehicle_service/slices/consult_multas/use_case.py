from __future__ import annotations

from typing import Protocol

from vehicle_service.adapters.outbound.simit_client import SimitClient
from vehicle_service.shared.cache_repository import VehicleCacheRepository, repository

from .schemas import ConsultMultasRequest, ConsultMultasResponse


class MultasClient(Protocol):
    async def consultar_multas(self, *, documento: str) -> dict[str, object]:
        ...


async def consult_multas(
    payload: ConsultMultasRequest,
    *,
    simit_client: MultasClient | None = None,
    cache_repository: VehicleCacheRepository | None = None,
) -> ConsultMultasResponse:
    active_cache = cache_repository or repository
    cached = active_cache.get_multas(documento=payload.documento)
    if cached is not None:
        return ConsultMultasResponse.model_validate(cached.payload)

    client = simit_client or SimitClient()
    data = await client.consultar_multas(documento=payload.documento)
    active_cache.save_multas(documento=payload.documento, payload=dict(data))
    return ConsultMultasResponse.model_validate(data)
