from __future__ import annotations

import os
from typing import Any

import httpx


class PlacesSummaryClient:
    def __init__(self, *, base_url: str | None = None, token: str | None = None) -> None:
        self.base_url = (base_url or os.getenv("PLACES_SERVICE_URL", "http://localhost:8085")).rstrip("/")
        self.token = token or os.getenv("INTERNAL_SERVICE_TOKEN", "")

    async def catalog_summary(self) -> dict[str, Any]:
        headers = {"Authorization": f"Bearer {self.token}"} if self.token else {}
        async with httpx.AsyncClient(timeout=10.0) as client:
            response = await client.get(
                f"{self.base_url}/internal/places/catalog/summary",
                headers=headers,
            )
            response.raise_for_status()
            return response.json()
