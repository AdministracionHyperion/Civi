from __future__ import annotations

import os
from typing import Any

import httpx


class SimitClient:
    def __init__(self, *, base_url: str | None = None, token: str | None = None) -> None:
        self.base_url = (base_url or os.getenv("SIMIT_SERVICE_URL", "http://localhost:8090")).rstrip("/")
        self.token = (token if token is not None else os.getenv("INTERNAL_SERVICE_TOKEN", "")).strip()
        if not self.token:
            raise RuntimeError("INTERNAL_SERVICE_TOKEN is required for SIMIT calls")

    @property
    def _headers(self) -> dict[str, str]:
        return {"Authorization": f"Bearer {self.token}"}

    async def consultar_multas(self, *, documento: str) -> dict[str, Any]:
        async with httpx.AsyncClient(timeout=90.0) as client:
            response = await client.post(
                f"{self.base_url}/internal/simit/multas",
                json={"documento": documento},
                headers=self._headers,
            )
            response.raise_for_status()
            return response.json()
