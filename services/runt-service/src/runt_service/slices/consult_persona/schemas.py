from __future__ import annotations

from typing import Any

from pydantic import BaseModel, Field


class RuntPersonaRequest(BaseModel):
    documento: str = Field(min_length=4, max_length=24)


class RuntPersonaResponse(BaseModel):
    ok: bool
    documentoTail: str
    data: dict[str, Any] | None = None
    error: str | None = None
    statusCode: int | None = None
    checkedAt: str
