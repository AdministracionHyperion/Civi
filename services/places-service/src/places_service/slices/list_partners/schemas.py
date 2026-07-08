from __future__ import annotations

from pydantic import BaseModel, Field


class PartnerSummary(BaseModel):
    id: str
    name: str
    city: str
    department: str
    kind: str


class ListPartnersResponse(BaseModel):
    success: bool = True
    partners: list[PartnerSummary] = Field(default_factory=list)
