from __future__ import annotations

import os
from datetime import date, timedelta
from typing import Protocol

from runt_service.adapters.outbound.browser_provider import BrowserRuntProvider
from runt_service.adapters.outbound.http_provider import HttpRuntProvider
from .schemas import RuntVigenciaRequest, RuntVigenciaResponse


class RuntProvider(Protocol):
    async def check_vigencia(self, payload: RuntVigenciaRequest) -> RuntVigenciaResponse:
        ...


async def check_vigencia(
    payload: RuntVigenciaRequest,
    *,
    provider: RuntProvider | None = None,
) -> RuntVigenciaResponse:
    if provider is not None:
        return await provider.check_vigencia(payload)

    mode = os.getenv("RUNT_PROVIDER_MODE", "local").strip().lower()
    if mode == "http":
        return await HttpRuntProvider.from_env().check_vigencia(payload)
    if mode == "browser":
        return await BrowserRuntProvider.from_env().check_vigencia(payload)
    if mode != "local":
        raise RuntimeError(f"unsupported RUNT provider mode: {mode}")

    return _local_vigencia(payload)


def _local_vigencia(payload: RuntVigenciaRequest) -> RuntVigenciaResponse:
    normalized_plate = payload.placa.strip().upper()
    checksum = sum(ord(char) for char in normalized_plate)
    soat_days = 30 + (checksum % 180)
    rtm_days = 15 + (checksum % 150)
    today = date.today()
    return RuntVigenciaResponse(
        placa=normalized_plate,
        vehiculo={"placa": normalized_plate, "estado": "normalizado_sin_consulta_externa"},
        soat={"vigente": True, "fechaVencimiento": (today + timedelta(days=soat_days)).isoformat()},
        rtm={"vigente": True, "fechaVencimiento": (today + timedelta(days=rtm_days)).isoformat()},
        alertas=[],
    )
