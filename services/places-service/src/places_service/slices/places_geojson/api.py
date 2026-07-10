from __future__ import annotations

from fastapi import APIRouter, Depends, Query

from civi_common import require_internal_token

from .use_case import places_geojson

router = APIRouter(tags=["places"])


@router.get(
    "/internal/places/geojson",
    dependencies=[Depends(require_internal_token)],
)
async def get_places_geojson(
    city: str = Query(default="Manizales", min_length=2),
    department: str | None = Query(default="Caldas"),
) -> dict:
    """GeoJSON FeatureCollection for map rendering (Manizales first)."""
    return places_geojson(city=city, department=department)
