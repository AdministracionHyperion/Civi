from __future__ import annotations

from typing import Any

from pydantic import BaseModel, Field


class ConsultMultasRequest(BaseModel):
    documento: str = Field(min_length=4, max_length=20)


class ConsultMultasResponse(BaseModel):
    success: bool
    documento_tail: str | None = Field(default=None, alias="documentoTail")
    tieneMultas: bool | None = None
    resumen: dict[str, Any] | None = None
    mensaje: str | None = None
    detalles: list[Any] = Field(default_factory=list)
