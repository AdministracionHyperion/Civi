from __future__ import annotations

import os
from typing import Any

import httpx


class NotificationClient:
    def __init__(self, *, base_url: str | None = None, token: str | None = None) -> None:
        self.base_url = (base_url or os.getenv("NOTIFICATION_SERVICE_URL", "http://localhost:8087")).rstrip("/")
        self.token = (token if token is not None else os.getenv("INTERNAL_SERVICE_TOKEN", "")).strip()
        if not self.token:
            raise RuntimeError("INTERNAL_SERVICE_TOKEN is required for notification service calls")

    @property
    def _headers(self) -> dict[str, str]:
        return {"Authorization": f"Bearer {self.token}"}

    async def schedule_reminder(
        self,
        *,
        user_key: str,
        to: str,
        body: str,
        remind_at: str,
    ) -> dict[str, Any]:
        async with httpx.AsyncClient(timeout=20.0) as client:
            response = await client.post(
                f"{self.base_url}/internal/notifications/reminders",
                json={"user_key": user_key, "to": to, "body": body, "remind_at": remind_at},
                headers=self._headers,
            )
            response.raise_for_status()
            return response.json()

    async def send_whatsapp_message(self, *, to: str, body: str) -> dict[str, Any]:
        async with httpx.AsyncClient(timeout=20.0) as client:
            response = await client.post(
                f"{self.base_url}/internal/notifications/whatsapp",
                json={"to": to, "body": body},
                headers=self._headers,
            )
            response.raise_for_status()
            return response.json()

    async def dispatch_outbox(self, *, limit: int = 10) -> dict[str, Any]:
        async with httpx.AsyncClient(timeout=20.0) as client:
            response = await client.post(
                f"{self.base_url}/internal/notifications/outbox/dispatch",
                params={"limit": limit},
                headers=self._headers,
            )
            response.raise_for_status()
            return response.json()
