from __future__ import annotations

from pydantic import BaseModel, Field


class GetInfraccionDetailRequest(BaseModel):
    codigo: str = Field(min_length=2, max_length=8)


class GetInfraccionDetailResponse(BaseModel):
    success: bool
    codigo: str
    categoria: str = ""
    smdlv: int | None = None
    monto_cop_2026: int | None = None
    descripcion: str = ""
    articulo: str = ""
    admite_descuento_curso: bool = False
    sancion_adicional: str | None = None
    consejo: str = ""
    message: str | None = None
