from __future__ import annotations

from pydantic import BaseModel, Field


class GetCityInfoRequest(BaseModel):
    city: str = Field(min_length=2, max_length=96)
    service_type: str = Field(default="tecnomecanica", min_length=2, max_length=64)


class GetCityInfoResponse(BaseModel):
    success: bool
    city: str
    service_type: str
    enabled: bool
    total_places: int = 0
    total_partners: int = 0
    notes: str = ""
    nearby_cities: list[str] = Field(default_factory=list)
    message: str | None = None
