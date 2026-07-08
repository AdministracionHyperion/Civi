from __future__ import annotations

import os
from typing import Any

import httpx


class KnowledgeClient:
    def __init__(self, *, base_url: str | None = None, token: str | None = None) -> None:
        self.base_url = (base_url or os.getenv("KNOWLEDGE_SERVICE_URL", "http://localhost:8094")).rstrip("/")
        self.token = (token if token is not None else os.getenv("INTERNAL_SERVICE_TOKEN", "")).strip()
        if not self.token:
            raise RuntimeError("INTERNAL_SERVICE_TOKEN is required for knowledge service calls")

    @property
    def _headers(self) -> dict[str, str]:
        return {"Authorization": f"Bearer {self.token}"}

    async def get_info(self, *, domain: str, topic: str) -> dict[str, Any]:
        async with httpx.AsyncClient(timeout=10.0) as client:
            response = await client.post(
                f"{self.base_url}/internal/knowledge/info",
                json={"domain": domain, "topic": topic},
                headers=self._headers,
            )
            response.raise_for_status()
            return response.json()

    async def get_city_info(self, *, city: str, service_type: str = "tecnomecanica") -> dict[str, Any]:
        async with httpx.AsyncClient(timeout=10.0) as client:
            response = await client.post(
                f"{self.base_url}/internal/knowledge/city",
                json={"city": city, "service_type": service_type},
                headers=self._headers,
            )
            response.raise_for_status()
            return response.json()
