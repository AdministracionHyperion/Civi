from __future__ import annotations

from pydantic import BaseModel, Field


class ListHistoryResponse(BaseModel):
    success: bool = True
    turns: list[dict[str, object]] = Field(default_factory=list)
