from __future__ import annotations

from pydantic import BaseModel, Field


class DashboardSummaryResponse(BaseModel):
    success: bool = True
    services: list[str] = Field(default_factory=list)
    service_statuses: list[dict[str, object]] = Field(default_factory=list)
    appointments_visible: bool = False
    note: str = "dashboard data must come through service contracts"
    places_catalog: dict[str, object] | None = None
