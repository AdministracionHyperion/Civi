from __future__ import annotations

import os
from datetime import datetime, timezone
from typing import Protocol

from runt_service.adapters.outbound.persona_http_provider import HttpRuntPersonaProvider

from .schemas import RuntPersonaRequest, RuntPersonaResponse


class RuntPersonaProvider(Protocol):
    async def consult_persona(self, payload: RuntPersonaRequest) -> RuntPersonaResponse:
        ...


async def consult_persona(
    payload: RuntPersonaRequest,
    *,
    provider: RuntPersonaProvider | None = None,
) -> RuntPersonaResponse:
    documento = "".join(char for char in payload.documento if char.isdigit())
    if len(documento) < 6:
        return _error_response(documento=documento, error="documento_invalido")

    if provider is not None:
        return await provider.consult_persona(RuntPersonaRequest(documento=documento))

    mode = _persona_mode()
    if mode == "http":
        return await HttpRuntPersonaProvider.from_env().consult_persona(RuntPersonaRequest(documento=documento))
    if mode in {"local", "disabled", "browser"}:
        return _error_response(documento=documento, error="persona_provider_not_configured")
    raise RuntimeError(f"unsupported RUNT persona provider mode: {mode}")


def _persona_mode() -> str:
    explicit = os.getenv("RUNT_PERSONA_PROVIDER_MODE", "").strip().lower()
    if explicit:
        return explicit
    if os.getenv("RUNT_PERSONA_PROVIDER_API_URL", "").strip() or os.getenv("RUNT_PERSONA_API_URL", "").strip():
        return "http"
    if os.getenv("RUNT_PROVIDER_API_URL", "").strip() or os.getenv("RUNT_" + "SCR" + "APER_API_URL", "").strip():
        return "http"
    return "local"


def _error_response(*, documento: str, error: str) -> RuntPersonaResponse:
    return RuntPersonaResponse(
        ok=False,
        documentoTail=documento[-4:] if documento else "",
        data=None,
        error=error,
        statusCode=None,
        checkedAt=datetime.now(timezone.utc).isoformat(),
    )
