from __future__ import annotations

import os
from typing import Any

import httpx
from fastapi import HTTPException


class PlacesCatalogUnavailable(Exception):
    """Raised when places-service cannot be reached or returns a server error."""


class PlacesClient:
    def __init__(self, *, base_url: str | None = None, token: str | None = None) -> None:
        self.base_url = (base_url or os.getenv("PLACES_SERVICE_URL", "http://localhost:8085")).rstrip("/")
        self.token = token or os.getenv("INTERNAL_SERVICE_TOKEN", "")

    def _headers(self) -> dict[str, str]:
        return {"Authorization": f"Bearer {self.token}"} if self.token else {}

    async def booking_eligibility(self, site_id: str) -> dict[str, Any]:
        try:
            async with httpx.AsyncClient(timeout=10.0) as client:
                response = await client.get(
                    f"{self.base_url}/internal/places/{site_id}/booking-eligibility",
                    headers=self._headers(),
                )
        except httpx.TimeoutException as exc:
            raise PlacesCatalogUnavailable("places_catalog_timeout") from exc
        except httpx.TransportError as exc:
            raise PlacesCatalogUnavailable("places_catalog_unreachable") from exc
        except httpx.HTTPError as exc:
            raise PlacesCatalogUnavailable("places_catalog_unavailable") from exc

        if response.status_code >= 500:
            raise PlacesCatalogUnavailable("places_catalog_unavailable")
        if response.status_code == 404:
            return {
                "site_id": site_id,
                "exists": False,
                "eligible_for_civi_booking": False,
                "eligibility_reason": "place_not_found",
            }
        try:
            response.raise_for_status()
            payload = response.json()
        except (httpx.HTTPError, ValueError) as exc:
            raise PlacesCatalogUnavailable("places_catalog_invalid_response") from exc
        if not isinstance(payload, dict):
            raise PlacesCatalogUnavailable("places_catalog_invalid_response")
        return payload
