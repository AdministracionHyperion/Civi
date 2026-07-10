from __future__ import annotations

import logging
from typing import Any, Protocol

from vehicle_service.adapters.outbound.manizales_client import ManizalesClient
from vehicle_service.adapters.outbound.simit_client import SimitClient
from vehicle_service.shared.cache_repository import VehicleCacheRepository, repository
from vehicle_service.shared.local_multas_portals import (
    normalize_city,
    portal_url_for_city,
    supports_live_local_consult,
)

from .schemas import ConsultMultasRequest, ConsultMultasResponse, LocalMultasInfo

logger = logging.getLogger("vehicle_service.consult_multas")


class MultasClient(Protocol):
    async def consultar_multas(self, *, documento: str) -> dict[str, object]:
        ...


async def consult_multas(
    payload: ConsultMultasRequest,
    *,
    simit_client: MultasClient | None = None,
    manizales_client: MultasClient | None = None,
    cache_repository: VehicleCacheRepository | None = None,
) -> ConsultMultasResponse:
    active_cache = cache_repository or repository
    city = normalize_city(payload.ciudad)
    portal_url = portal_url_for_city(payload.ciudad)

    cached = active_cache.get_multas(documento=payload.documento)
    if cached is not None and not city:
        return ConsultMultasResponse.model_validate(_ensure_wrapped(cached.payload, portal_url=portal_url))

    client = simit_client or SimitClient()
    simit_data = await client.consultar_multas(documento=payload.documento)
    if not isinstance(simit_data, dict):
        simit_data = {}

    local = LocalMultasInfo(
        city=city,
        source=None,
        consulted=False,
        portalUrl=portal_url,
    )

    if supports_live_local_consult(city):
        local.source = "manizales"
        try:
            regional = manizales_client or ManizalesClient()
            local_data = await regional.consultar_multas(documento=payload.documento)
            if isinstance(local_data, dict):
                local.consulted = True
                local.tieneMultas = bool(local_data.get("tieneMultas"))
                local.resumen = local_data.get("resumen") if isinstance(local_data.get("resumen"), dict) else None
                local.mensaje = str(local_data.get("mensaje") or "") or None
                detalles = local_data.get("detalles")
                local.detalles = list(detalles) if isinstance(detalles, list) else []
        except Exception:
            logger.exception("Manizales local multas consult failed; continuing with SIMIT only")
            local.consulted = False
            local.mensaje = "No pude consultar el portal de Manizales en este momento."

    response_payload = {
        "success": True,
        "documentoTail": simit_data.get("documentoTail") or simit_data.get("documento_tail"),
        "tieneMultas": bool(simit_data.get("tieneMultas")),
        "resumen": simit_data.get("resumen"),
        "mensaje": simit_data.get("mensaje"),
        "detalles": simit_data.get("detalles") or [],
        "simit": {
            "tieneMultas": bool(simit_data.get("tieneMultas")),
            "resumen": simit_data.get("resumen"),
            "mensaje": simit_data.get("mensaje"),
            "detalles": simit_data.get("detalles") or [],
            "documentoTail": simit_data.get("documentoTail") or simit_data.get("documento_tail"),
        },
        "local": local.model_dump(by_alias=True),
    }

    # Cache only the SIMIT-centric payload when no city-specific consult was requested.
    if not city:
        active_cache.save_multas(documento=payload.documento, payload=dict(response_payload))

    return ConsultMultasResponse.model_validate(response_payload)


def _ensure_wrapped(payload: dict[str, Any], *, portal_url: str | None) -> dict[str, Any]:
    if isinstance(payload.get("simit"), dict):
        if portal_url and isinstance(payload.get("local"), dict):
            local = dict(payload["local"])
            local.setdefault("portalUrl", portal_url)
            payload = dict(payload)
            payload["local"] = local
        return payload
    return {
        "success": bool(payload.get("success", True)),
        "documentoTail": payload.get("documentoTail") or payload.get("documento_tail"),
        "tieneMultas": payload.get("tieneMultas"),
        "resumen": payload.get("resumen"),
        "mensaje": payload.get("mensaje"),
        "detalles": payload.get("detalles") or [],
        "simit": {
            "tieneMultas": payload.get("tieneMultas"),
            "resumen": payload.get("resumen"),
            "mensaje": payload.get("mensaje"),
            "detalles": payload.get("detalles") or [],
            "documentoTail": payload.get("documentoTail") or payload.get("documento_tail"),
        },
        "local": {
            "city": None,
            "source": None,
            "consulted": False,
            "portalUrl": portal_url,
            "tieneMultas": None,
            "resumen": None,
            "mensaje": None,
            "detalles": [],
        },
    }
