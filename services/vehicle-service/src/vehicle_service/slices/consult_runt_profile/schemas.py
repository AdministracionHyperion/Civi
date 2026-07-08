from __future__ import annotations

from typing import Any

from pydantic import BaseModel, Field


class ConsultRuntProfileRequest(BaseModel):
    documento: str = Field(min_length=4, max_length=24)


class ConsultRuntProfileResponse(BaseModel):
    ok: bool
    documentoTail: str
    data: dict[str, Any] | None = None
    error: str | None = None
    statusCode: int | None = None
    checkedAt: str
