from __future__ import annotations

from knowledge_service.shared.knowledge_base import get_city_coverage, normalize_key

from .schemas import GetCityInfoRequest, GetCityInfoResponse


async def get_city_info(payload: GetCityInfoRequest) -> GetCityInfoResponse:
    service_type = normalize_key(payload.service_type)
    if service_type not in {"tecnomecanica", "tecno", "rtm", "cda"}:
        return GetCityInfoResponse(
            success=False,
            city=payload.city.strip(),
            service_type=service_type,
            enabled=False,
            message="Servicio de ciudad no soportado.",
        )

    coverage = get_city_coverage(payload.city)
    enabled = bool(coverage["enabled"])
    return GetCityInfoResponse(
        success=True,
        city=str(coverage["city"]),
        service_type="tecnomecanica",
        enabled=enabled,
        total_places=int(coverage["total_places"]),
        total_partners=int(coverage["total_partners"]),
        notes=str(coverage["notes"]),
        nearby_cities=list(coverage.get("nearby_cities") or []),
        message=None if enabled else "Ciudad sin cobertura operativa cargada.",
    )
