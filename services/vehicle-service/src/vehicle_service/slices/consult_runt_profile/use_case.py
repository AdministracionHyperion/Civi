from __future__ import annotations

from typing import Protocol

from vehicle_service.adapters.outbound.runt_client import RuntClient

from .schemas import ConsultRuntProfileRequest, ConsultRuntProfileResponse


class RuntProfileClient(Protocol):
    async def consultar_persona(self, *, documento: str) -> dict[str, object]:
        ...


async def consult_runt_profile(
    payload: ConsultRuntProfileRequest,
    *,
    runt_client: RuntProfileClient | None = None,
) -> ConsultRuntProfileResponse:
    client = runt_client or RuntClient()
    data = await client.consultar_persona(documento=payload.documento)
    return ConsultRuntProfileResponse.model_validate(data)
