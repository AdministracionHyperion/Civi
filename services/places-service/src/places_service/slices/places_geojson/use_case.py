from __future__ import annotations

from places_service.adapters.outbound.catalog_repository import catalog_repository_from_env
from places_service.domain.models import CONFIRMED_VALIDATION_STATUSES


def places_geojson(*, city: str, department: str | None = None) -> dict:
    repo = catalog_repository_from_env()
    if repo is None:
        return {
            "type": "FeatureCollection",
            "features": [],
            "meta": {
                "city": city,
                "department": department,
                "count": 0,
                "error": "places_database_unconfigured",
            },
        }
    features = repo.list_geojson_features(city=city, department=department)
    return {
        "type": "FeatureCollection",
        "features": features,
        "meta": {
            "city": city,
            "department": department,
            "count": len(features),
            "confirmed_statuses": sorted(CONFIRMED_VALIDATION_STATUSES),
        },
    }
