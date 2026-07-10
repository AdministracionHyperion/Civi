from __future__ import annotations

from typing import Any

from pydantic import BaseModel, Field


class ConsultMultasRequest(BaseModel):
    documento: str = Field(min_length=4, max_length=20)
    ciudad: str | None = Field(default=None, max_length=64)


class LocalMultasInfo(BaseModel):
    city: str | None = None
    source: str | None = None
    consulted: bool = False
    tieneMultas: bool | None = None
    resumen: dict[str, Any] | None = None
    mensaje: str | None = None
    portalUrl: str | None = None
    detalles: list[Any] = Field(default_factory=list)


class ConsultMultasResponse(BaseModel):
    success: bool
    documento_tail: str | None = Field(default=None, alias="documentoTail")
    tieneMultas: bool | None = None
    resumen: dict[str, Any] | None = None
    mensaje: str | None = None
    detalles: list[Any] = Field(default_factory=list)
    simit: dict[str, Any] | None = None
    local: LocalMultasInfo | None = None

    model_config = {"populate_by_name": True}
