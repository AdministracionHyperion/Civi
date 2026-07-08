from __future__ import annotations

from typing import Any

from pydantic import BaseModel, Field


class RuntVigenciaRequest(BaseModel):
    placa: str = Field(min_length=5, max_length=8)
    documento: str = Field(min_length=4, max_length=24)
    tipo_documento: str = Field(default="CC", min_length=1, max_length=8, alias="tipoDocumento")
    forzar_actualizacion: bool = Field(default=False, alias="forzarActualizacion")


class RuntVigenciaResponse(BaseModel):
    success: bool = True
    placa: str
    vehiculo: dict[str, Any]
    soat: dict[str, Any]
    rtm: dict[str, Any]
    multas: dict[str, Any] | None = None
    alertas: list[dict[str, Any]] = Field(default_factory=list)
    fromCache: bool = False
