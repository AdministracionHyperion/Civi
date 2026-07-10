from __future__ import annotations

from pydantic import BaseModel, Field


class FindNearestPlaceRequest(BaseModel):
    procedure: str = Field(min_length=2)
    city: str | None = None
    lat: float | None = None
    lng: float | None = None
    limit: int = Field(default=3, ge=1, le=10)
    municipality_code: str | None = None


class PlaceResult(BaseModel):
    id: str
    name: str
    address: str
    city: str
    department: str
    kind: str
    distance_km: float | None = None
    municipality_code: str | None = None
    status: str | None = None
    status_verified: bool | None = None
    is_partner: bool | None = None
    is_bookable: bool | None = None
    booking_mode: str | None = None
    location_precision: str | None = None
    data_quality: float | None = None
    contact_available: bool | None = None
    # Geocode surface. `confirmed_*` may be presented as confirmed; approximate must not.
    lat: float | None = None
    lng: float | None = None
    confidence: float | None = None
    provider: str | None = None
    precision: str | None = None
    validation_status: str | None = None
    location_confirmed: bool | None = None


class FindNearestPlaceResponse(BaseModel):
    success: bool
    places: list[PlaceResult] = Field(default_factory=list)
    source: str = "catalog"
    match_scope: str | None = None
    resolved_location: dict | None = None
    no_results_reason: str | None = None
    search_radius_km: float | None = None
    total_candidates: int | None = None
    geocoded_candidates: int | None = None
