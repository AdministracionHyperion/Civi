from __future__ import annotations

from pydantic import BaseModel, Field


class ManagePartnersResponse(BaseModel):
    success: bool = True
    managed_by: str = "places-service"
    allowed_operations: list[str] = Field(default_factory=lambda: ["read_via_places_service"])
