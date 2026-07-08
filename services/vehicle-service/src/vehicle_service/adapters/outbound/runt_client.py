from __future__ import annotations

import os
from typing import Any

import httpx


class RuntClient:
    def __init__(self, *, base_url: str | None = None, token: str | None = None) -> None:
        self.base_url = (base_url or os.getenv("RUNT_SERVICE_URL", "http://localhost:8084")).rstrip("/")
        self.token = (token if token is not None else os.getenv("INTERNAL_SERVICE_TOKEN", "")).strip()
        if not self.token:
            raise RuntimeError("INTERNAL_SERVICE_TOKEN is required for RUNT calls")

    @property
    def _headers(self) -> dict[str, str]:
        return {"Authorization": f"Bearer {self.token}"}

    async def consultar_vigencia(
        self,
        *,
        placa: str,
        documento: str,
        tipo_documento: str = "CC",
        forzar_actualizacion: bool = False,
    ) -> dict[str, Any]:
        payload = {
            "placa": placa,
            "documento": documento,
            "tipoDocumento": tipo_documento,
            "forzarActualizacion": forzar_actualizacion,
        }
        async with httpx.AsyncClient(timeout=120.0) as client:
            response = await client.post(
                f"{self.base_url}/internal/runt/vigencia",
                json=payload,
                headers=self._headers,
            )
            response.raise_for_status()
            return response.json()

    async def consultar_persona(self, *, documento: str) -> dict[str, Any]:
        async with httpx.AsyncClient(timeout=120.0) as client:
            response = await client.post(
                f"{self.base_url}/internal/runt/persona",
                json={"documento": documento},
                headers=self._headers,
            )
            response.raise_for_status()
            return response.json()
