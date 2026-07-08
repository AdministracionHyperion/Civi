from __future__ import annotations

from typing import Any

from pydantic import BaseModel, Field


class CheckVigenciaRequest(BaseModel):
    placa: str = Field(min_length=5, max_length=8)
    documento: str = Field(min_length=4, max_length=20)
    tipo_documento: str = Field(default="CC", alias="tipoDocumento")
    forzar_actualizacion: bool = Field(default=False, alias="forzarActualizacion")


class CheckVigenciaResponse(BaseModel):
    success: bool
    placa: str | None = None
    vehiculo: dict[str, Any] | None = None
    soat: dict[str, Any] | None = None
    rtm: dict[str, Any] | None = None
    multas: dict[str, Any] | None = None
    alertas: list[dict[str, Any]] = Field(default_factory=list)
    from_cache: bool = Field(default=False, alias="fromCache")
