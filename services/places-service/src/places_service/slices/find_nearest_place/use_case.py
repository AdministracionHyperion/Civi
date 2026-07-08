from __future__ import annotations

import math

from places_service.shared.catalog import Place
from places_service.shared.repository import PlacesRepository, repository

from .schemas import FindNearestPlaceRequest, FindNearestPlaceResponse, PlaceResult


KIND_BY_PROCEDURE = {
    "tecnomecanica": "CDA",
    "tecnomecánica": "CDA",
    "tecno": "CDA",
    "rtm": "CDA",
    "licencia": "CEA",
    "licencia_primera": "CEA",
    "renovacion_licencia": "CRC",
    "renovación_licencia": "CRC",
    "curso_multa": "CIA",
    "multa": "CIA",
    "comparendo": "CIA",
}


def _normalize(value: str | None) -> str:
    return (value or "").strip().lower()


def _kind_for(procedure: str) -> str | None:
    proc = _normalize(procedure)
    return KIND_BY_PROCEDURE.get(proc, procedure.upper() if len(procedure) <= 4 else None)


def _distance_km(lat1: float, lng1: float, lat2: float, lng2: float) -> float:
    radius = 6371.0
    dlat = math.radians(lat2 - lat1)
    dlng = math.radians(lng2 - lng1)
    a = (
        math.sin(dlat / 2) ** 2
        + math.cos(math.radians(lat1))
        * math.cos(math.radians(lat2))
        * math.sin(dlng / 2) ** 2
    )
    return radius * 2 * math.atan2(math.sqrt(a), math.sqrt(1 - a))


def _to_result(place: Place, *, distance_km: float | None = None) -> PlaceResult:
    return PlaceResult(
        id=place.id,
        name=place.name,
        address=place.address,
        city=place.city,
        department=place.department,
        kind=place.kind,
        distance_km=round(distance_km, 2) if distance_km is not None else None,
    )


async def find_nearest_place(
    payload: FindNearestPlaceRequest,
    *,
    places_repository: PlacesRepository | None = None,
) -> FindNearestPlaceResponse:
    kind = _kind_for(payload.procedure)
    city = _normalize(payload.city)
    available_places = (places_repository or repository).list_all()

    candidates = [
        place
        for place in available_places
        if (kind is None or place.kind.upper() == kind.upper())
        and (not city or _normalize(place.city) == city)
    ]

    if not candidates and kind:
        candidates = [place for place in available_places if place.kind.upper() == kind.upper()]

    if payload.lat is not None and payload.lng is not None:
        ranked = sorted(
            (
                (_distance_km(payload.lat, payload.lng, place.lat, place.lng), place)
                for place in candidates
            ),
            key=lambda item: (item[0], not item[1].is_partner),
        )
        places = [_to_result(place, distance_km=distance) for distance, place in ranked[: payload.limit]]
    else:
        ranked_places = sorted(candidates, key=lambda place: (not place.is_partner, place.city, place.name))
        places = [_to_result(place) for place in ranked_places[: payload.limit]]

    return FindNearestPlaceResponse(success=True, places=places)
