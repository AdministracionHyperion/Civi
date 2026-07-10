from __future__ import annotations

import os
from typing import Any

import httpx


class QuoteClient:
    def __init__(self, *, base_url: str | None = None, token: str | None = None) -> None:
        self.base_url = (base_url or os.getenv("QUOTE_SERVICE_URL", "http://localhost:8091")).rstrip("/")
        self.token = (token if token is not None else os.getenv("INTERNAL_SERVICE_TOKEN", "")).strip()
        if not self.token:
            raise RuntimeError("INTERNAL_SERVICE_TOKEN is required for quote service calls")

    @property
    def _headers(self) -> dict[str, str]:
        return {"Authorization": f"Bearer {self.token}"}

    async def create(
        self,
        *,
        service_type: str,
        city: str | None = None,
        vehicle_type: str | None = None,
        cilindraje: int | None = None,
        modelo: int | None = None,
        categoria: str | None = None,
        consulta: str | None = None,
        codigo: str | None = None,
        variable: str | None = None,
    ) -> dict[str, Any]:
        payload = {
            "service_type": service_type,
            "city": city,
            "vehicle_type": vehicle_type,
            "cilindraje": cilindraje,
            "modelo": modelo,
            "categoria": categoria,
            "consulta": consulta,
            "codigo": codigo,
            "variable": variable,
        }
        async with httpx.AsyncClient(timeout=20.0) as client:
            response = await client.post(
                f"{self.base_url}/internal/quotes",
                json={key: value for key, value in payload.items() if value is not None},
                headers=self._headers,
            )
            response.raise_for_status()
            return response.json()

    async def get_infraccion_detail(self, *, codigo: str) -> dict[str, Any]:
        async with httpx.AsyncClient(timeout=20.0) as client:
            response = await client.post(
                f"{self.base_url}/internal/quotes/infraccion/detail",
                json={"codigo": codigo},
                headers=self._headers,
            )
            response.raise_for_status()
            return response.json()
