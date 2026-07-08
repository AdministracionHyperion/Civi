from __future__ import annotations

from pydantic import BaseModel, Field


class ListAuditEventsResponse(BaseModel):
    success: bool = True
    events: list[dict[str, object]] = Field(default_factory=list)
