from __future__ import annotations

from pydantic import BaseModel, Field


class OpsContactResponse(BaseModel):
    site_id: str
    name: str
    e164: str


class OpsContactLookupRequest(BaseModel):
    e164: str = Field(min_length=10, max_length=32)
