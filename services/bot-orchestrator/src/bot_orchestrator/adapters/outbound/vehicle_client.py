from __future__ import annotations

import os
from typing import Any

import httpx


class VehicleClient:
    def __init__(self, *, base_url: str | None = None, token: str | None = None) -> None:
        self.base_url = (base_url or os.getenv("VEHICLE_SERVICE_URL", "http://localhost:8083")).rstrip("/")
        self.token = (token if token is not None else os.getenv("INTERNAL_SERVICE_TOKEN", "")).strip()
        if not self.token:
            raise RuntimeError("INTERNAL_SERVICE_TOKEN is required for vehicle service calls")

    @property
    def _headers(self) -> dict[str, str]:
        return {"Authorization": f"Bearer {self.token}"}

    async def check_vigencia(
        self,
        *,
        placa: str,
        documento: str,
        tipo_documento: str = "CC",
    ) -> dict[str, Any]:
        async with httpx.AsyncClient(timeout=130.0) as client:
            response = await client.post(
                f"{self.base_url}/internal/vehicles/vigencia",
                json={
                    "placa": placa,
                    "documento": documento,
                    "tipoDocumento": tipo_documento,
                },
                headers=self._headers,
            )
            response.raise_for_status()
            return response.json()

    async def consult_multas(self, *, documento: str) -> dict[str, Any]:
        async with httpx.AsyncClient(timeout=100.0) as client:
            response = await client.post(
                f"{self.base_url}/internal/vehicles/multas",
                json={"documento": documento},
                headers=self._headers,
            )
            response.raise_for_status()
            return response.json()

    async def consult_runt_profile(self, *, documento: str) -> dict[str, Any]:
        async with httpx.AsyncClient(timeout=120.0) as client:
            response = await client.post(
                f"{self.base_url}/internal/vehicles/runt-profile",
                json={"documento": documento},
                headers=self._headers,
            )
            response.raise_for_status()
            return response.json()
