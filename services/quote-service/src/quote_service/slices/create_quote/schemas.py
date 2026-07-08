from __future__ import annotations

from pydantic import BaseModel, Field


class CreateQuoteRequest(BaseModel):
    service_type: str = Field(min_length=2, max_length=64)
    vehicle_type: str | None = Field(default=None, max_length=64)
    city: str | None = Field(default=None, max_length=96)
    cilindraje: int | None = Field(default=None, ge=1, le=9999)
    modelo: int | None = Field(default=None, ge=1950, le=2100)
    categoria: str | None = Field(default=None, max_length=64)
    consulta: str | None = Field(default=None, max_length=500)
    codigo: str | None = Field(default=None, max_length=8)
    variable: str | None = Field(default=None, max_length=32)
    year: int | None = Field(default=None, ge=2025, le=2100)


class CreateQuoteResponse(BaseModel):
    service_type: str
    price_min: int
    price_max: int
    currency: str = "COP"
    disclaimer: str
    quote_type: str = "range"
    price_cop: int | None = None
    details: dict[str, object] = Field(default_factory=dict)
    message: str | None = None
    options: list[dict[str, object]] = Field(default_factory=list)
