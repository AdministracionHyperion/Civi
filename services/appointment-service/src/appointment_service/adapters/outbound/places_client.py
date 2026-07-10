from __future__ import annotations

import os
from typing import Any

import httpx


class PlacesClient:
    def __init__(self, *, base_url: str | None = None, token: str | None = None) -> None:
        self.base_url = (base_url or os.getenv("PLACES_SERVICE_URL", "http://localhost:8085")).rstrip("/")
        self.token = token or os.getenv("INTERNAL_SERVICE_TOKEN", "")

    def _headers(self) -> dict[str, str]:
        return {"Authorization": f"Bearer {self.token}"} if self.token else {}

    async def booking_eligibility(self, site_id: str) -> dict[str, Any]:
        async with httpx.AsyncClient(timeout=10.0) as client:
            response = await client.get(
                f"{self.base_url}/internal/places/{site_id}/booking-eligibility",
                headers=self._headers(),
            )
            response.raise_for_status()
            return response.json()
