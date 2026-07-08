from __future__ import annotations

import os
from typing import Protocol

from simit_service.adapters.outbound.browser_provider import BrowserSimitProvider
from simit_service.adapters.outbound.http_provider import HttpSimitProvider
from .schemas import SimitMultasRequest, SimitMultasResponse


class SimitProvider(Protocol):
    async def consult_multas(self, payload: SimitMultasRequest) -> SimitMultasResponse:
        ...


async def consult_multas(
    payload: SimitMultasRequest,
    *,
    provider: SimitProvider | None = None,
) -> SimitMultasResponse:
    if provider is not None:
        return await provider.consult_multas(payload)

    mode = os.getenv("SIMIT_PROVIDER_MODE", "local").strip().lower()
    if mode == "http":
        return await HttpSimitProvider.from_env().consult_multas(payload)
    if mode == "browser":
        return await BrowserSimitProvider.from_env().consult_multas(payload)
    if mode != "local":
        raise RuntimeError(f"unsupported SIMIT provider mode: {mode}")

    return _local_multas(payload)


def _local_multas(payload: SimitMultasRequest) -> SimitMultasResponse:
    normalized = "".join(char for char in payload.documento if char.isdigit())
    checksum = sum(int(char) for char in normalized) if normalized else 0
    has_pending = checksum % 7 == 0 and checksum != 0
    return SimitMultasResponse(
        documentoTail=normalized[-4:] if normalized else "",
        tieneMultas=has_pending,
        resumen={
            "comparendos": 1 if has_pending else 0,
            "multas": 1 if has_pending else 0,
            "total": 250000 if has_pending else 0,
        },
        mensaje="Consulta normalizada sin proveedor externo activo.",
        detalles=[],
    )
