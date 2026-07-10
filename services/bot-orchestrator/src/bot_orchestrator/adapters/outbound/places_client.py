from __future__ import annotations

import os
from typing import Any

import httpx


class PlacesClient:
    def __init__(self, *, base_url: str | None = None, token: str | None = None) -> None:
        self.base_url = (base_url or os.getenv("PLACES_SERVICE_URL", "http://localhost:8085")).rstrip("/")
        self.token = (token if token is not None else os.getenv("INTERNAL_SERVICE_TOKEN", "")).strip()
        if not self.token:
            raise RuntimeError("INTERNAL_SERVICE_TOKEN is required for places service calls")

    @property
    def _headers(self) -> dict[str, str]:
        return {"Authorization": f"Bearer {self.token}"}

    async def find_nearest(
        self,
        *,
        procedure: str,
        city: str | None = None,
        lat: float | None = None,
        lng: float | None = None,
    ) -> dict[str, Any]:
        payload = {"procedure": procedure, "city": city, "lat": lat, "lng": lng, "limit": 5}
        async with httpx.AsyncClient(timeout=20.0) as client:
            response = await client.post(
                f"{self.base_url}/internal/places/nearest",
                json=payload,
                headers=self._headers,
            )
            response.raise_for_status()
            return response.json()

    async def lookup_ops_contact(self, *, e164: str) -> dict[str, Any] | None:
        async with httpx.AsyncClient(timeout=20.0) as client:
            response = await client.post(
                f"{self.base_url}/internal/places/ops-contact/lookup",
                json={"e164": e164},
                headers=self._headers,
            )
            if response.status_code == 404:
                return None
            response.raise_for_status()
            return response.json()
