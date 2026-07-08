from __future__ import annotations

from pydantic import BaseModel, Field


class FindNearestPlaceRequest(BaseModel):
    procedure: str = Field(min_length=2)
    city: str | None = None
    lat: float | None = None
    lng: float | None = None
    limit: int = Field(default=3, ge=1, le=10)


class PlaceResult(BaseModel):
    id: str
    name: str
    address: str
    city: str
    department: str
    kind: str
    distance_km: float | None = None


class FindNearestPlaceResponse(BaseModel):
    success: bool
    places: list[PlaceResult] = Field(default_factory=list)
    source: str = "catalog"
