from __future__ import annotations

import math
import os

from places_service.adapters.outbound.catalog_repository import catalog_repository_from_env
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

EXCLUDED_STATUSES = frozenset({"retired", "inactive", "suspended"})


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


def _search_radius_km() -> float:
    raw = os.getenv("PLACES_SEARCH_RADIUS_KM", "40").strip()
    try:
        return max(1.0, float(raw))
    except ValueError:
        return 40.0


def _to_result(place: Place, *, distance_km: float | None = None) -> PlaceResult:
    return PlaceResult(
        id=place.id,
        name=place.name,
        address=place.address,
        city=place.city,
        department=place.department,
        kind=place.kind,
        distance_km=round(distance_km, 2) if distance_km is not None else None,
        status=getattr(place, "status", None),
        is_partner=getattr(place, "is_partner", None),
        is_bookable=getattr(place, "is_bookable", False),
        booking_mode=getattr(place, "booking_mode", "information_only"),
        contact_available=bool(getattr(place, "phone", None)),
    )


def _is_searchable(place: Place) -> bool:
    status = (getattr(place, "status", None) or "unknown").strip().lower()
    return status not in EXCLUDED_STATUSES


def _has_coords(place: Place) -> bool:
    return place.lat is not None and place.lng is not None


async def find_nearest_place(
    payload: FindNearestPlaceRequest,
    *,
    places_repository: PlacesRepository | None = None,
) -> FindNearestPlaceResponse:
    kind = _kind_for(payload.procedure)
    radius_km = _search_radius_km()

    catalog_repo = catalog_repository_from_env()
    if catalog_repo is not None and places_repository is None:
        result = catalog_repo.search_nearest(
            actor_type=kind,
            city=payload.city,
            municipality_code=payload.municipality_code,
            lat=payload.lat,
            lng=payload.lng,
            limit=payload.limit,
            radius_km=radius_km,
        )
        places = [PlaceResult(**item) for item in result["places"]]
        return FindNearestPlaceResponse(
            success=True,
            places=places,
            source="places_sites",
            match_scope=result.get("match_scope"),
            resolved_location=result.get("resolved_location"),
            no_results_reason=result.get("no_results_reason"),
            search_radius_km=result.get("search_radius_km"),
            total_candidates=result.get("total_candidates"),
            geocoded_candidates=result.get("geocoded_candidates"),
        )

    # Memory/sample fallback for unit tests — still NO national fallback
    city = _normalize(payload.city)
    available_places = [place for place in (places_repository or repository).list_all() if _is_searchable(place)]
    candidates = [
        place
        for place in available_places
        if (kind is None or place.kind.upper() == kind.upper())
        and (not city or _normalize(place.city) == city)
    ]

    if payload.lat is not None and payload.lng is not None:
        from civi_common.geo import is_colombia_latlng

        if not is_colombia_latlng(payload.lat, payload.lng):
            return FindNearestPlaceResponse(
                success=True,
                places=[],
                match_scope="gps",
                resolved_location={"lat": payload.lat, "lng": payload.lng},
                no_results_reason="coordinates_outside_colombia",
                search_radius_km=radius_km,
                total_candidates=0,
                geocoded_candidates=0,
            )
        geo_candidates = [
            place
            for place in candidates
            if _has_coords(place) and is_colombia_latlng(place.lat or 0.0, place.lng or 0.0)
        ]
        ranked = []
        for place in geo_candidates:
            distance = _distance_km(payload.lat, payload.lng, place.lat or 0.0, place.lng or 0.0)
            if distance <= radius_km:
                ranked.append((distance, place))
        ranked.sort(key=lambda item: (item[0], not getattr(item[1], "is_bookable", False), not item[1].is_partner))
        places = [_to_result(place, distance_km=distance) for distance, place in ranked[: payload.limit]]
        return FindNearestPlaceResponse(
            success=True,
            places=places,
            match_scope="gps",
            resolved_location={"lat": payload.lat, "lng": payload.lng},
            no_results_reason=None if places else "no_sites_within_radius",
            search_radius_km=radius_km,
            total_candidates=len(ranked),
            geocoded_candidates=len(geo_candidates),
        )

    if city:
        ranked_places = sorted(
            candidates,
            key=lambda place: (
                not getattr(place, "is_bookable", False),
                not place.is_partner,
                place.city,
                place.name,
            ),
        )
        places = [_to_result(place) for place in ranked_places[: payload.limit]]
        return FindNearestPlaceResponse(
            success=True,
            places=places,
            match_scope="municipality_name",
            resolved_location={"city": payload.city},
            no_results_reason=None if places else "no_coverage_in_municipality",
            search_radius_km=radius_km,
            total_candidates=len(candidates),
            geocoded_candidates=sum(1 for p in candidates if _has_coords(p)),
        )

    return FindNearestPlaceResponse(
        success=True,
        places=[],
        match_scope="none",
        no_results_reason="city_or_coordinates_required",
        search_radius_km=radius_km,
        total_candidates=0,
        geocoded_candidates=0,
    )
