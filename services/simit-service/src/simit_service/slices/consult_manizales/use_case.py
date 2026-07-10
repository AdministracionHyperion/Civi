from __future__ import annotations

import os
from typing import Protocol

from simit_service.adapters.outbound.manizales_provider import (
    BrowserManizalesProvider,
    local_manizales_multas,
)
from simit_service.slices.consult_multas.schemas import SimitMultasRequest, SimitMultasResponse


class ManizalesProvider(Protocol):
    async def consult_multas(self, payload: SimitMultasRequest) -> SimitMultasResponse:
        ...


async def consult_manizales_multas(
    payload: SimitMultasRequest,
    *,
    provider: ManizalesProvider | None = None,
) -> SimitMultasResponse:
    if provider is not None:
        return await provider.consult_multas(payload)

    mode = os.getenv("MANIZALES_PROVIDER_MODE", os.getenv("SIMIT_PROVIDER_MODE", "local")).strip().lower()
    if mode == "browser":
        return await BrowserManizalesProvider.from_env().consult_multas(payload)
    if mode == "local":
        return local_manizales_multas(payload)
    raise RuntimeError(f"unsupported Manizales provider mode: {mode}")
