from __future__ import annotations

from pydantic import BaseModel, Field


class SimitMultasRequest(BaseModel):
    documento: str = Field(min_length=4, max_length=24)


class SimitMultasResponse(BaseModel):
    success: bool = True
    documentoTail: str
    tieneMultas: bool
    resumen: dict[str, int]
    mensaje: str
    detalles: list[dict[str, object]] = Field(default_factory=list)
