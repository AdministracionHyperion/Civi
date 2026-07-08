from __future__ import annotations

import os
from typing import Any

import httpx


class AppointmentClient:
    def __init__(self, *, base_url: str | None = None, token: str | None = None) -> None:
        self.base_url = (base_url or os.getenv("APPOINTMENT_SERVICE_URL", "http://localhost:8086")).rstrip("/")
        self.token = (token if token is not None else os.getenv("INTERNAL_SERVICE_TOKEN", "")).strip()
        if not self.token:
            raise RuntimeError("INTERNAL_SERVICE_TOKEN is required for appointment service calls")

    @property
    def _headers(self) -> dict[str, str]:
        return {"Authorization": f"Bearer {self.token}"}

    async def create(
        self,
        *,
        user_key: str,
        procedure: str,
        starts_at: str,
        place: dict[str, Any],
        notification_to: str | None = None,
    ) -> dict[str, Any]:
        payload: dict[str, Any] = {
            "user_key": user_key,
            "procedure": procedure,
            "starts_at": starts_at,
            "place": {
                "id": place["id"],
                "name": place["name"],
                "address": place["address"],
                "city": place["city"],
            },
        }
        if notification_to:
            payload["notification_to"] = notification_to

        async with httpx.AsyncClient(timeout=20.0) as client:
            response = await client.post(
                f"{self.base_url}/internal/appointments",
                json=payload,
                headers=self._headers,
            )
            response.raise_for_status()
            return response.json()

    async def list_for_user(self, *, user_key: str) -> dict[str, Any]:
        async with httpx.AsyncClient(timeout=20.0) as client:
            response = await client.get(
                f"{self.base_url}/internal/appointments",
                params={"user_key": user_key},
                headers=self._headers,
            )
            response.raise_for_status()
            return response.json()

    async def cancel(self, *, user_key: str, appointment_id: int) -> dict[str, Any]:
        async with httpx.AsyncClient(timeout=20.0) as client:
            response = await client.delete(
                f"{self.base_url}/internal/appointments/{appointment_id}",
                params={"user_key": user_key},
                headers=self._headers,
            )
            response.raise_for_status()
            return response.json()
