from __future__ import annotations

from pydantic import BaseModel


class PlaceDetailResponse(BaseModel):
    success: bool
    place: dict | None = None
    error: str | None = None
