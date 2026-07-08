from __future__ import annotations

from pydantic import BaseModel, Field


class DispatchOutboxResponse(BaseModel):
    success: bool = True
    dispatched: list[dict[str, object]] = Field(default_factory=list)
