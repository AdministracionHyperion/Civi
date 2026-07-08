from __future__ import annotations

import os
from typing import Any

import httpx


class HandoffClient:
    def __init__(self, *, base_url: str | None = None, token: str | None = None) -> None:
        self.base_url = (base_url or os.getenv("HANDOFF_SERVICE_URL", "http://localhost:8093")).rstrip("/")
        self.token = (token if token is not None else os.getenv("INTERNAL_SERVICE_TOKEN", "")).strip()
        if not self.token:
            raise RuntimeError("INTERNAL_SERVICE_TOKEN is required for handoff service calls")

    @property
    def _headers(self) -> dict[str, str]:
        return {"Authorization": f"Bearer {self.token}"}

    async def create(self, *, user_key: str, reason: str, channel: str) -> dict[str, Any]:
        async with httpx.AsyncClient(timeout=20.0) as client:
            response = await client.post(
                f"{self.base_url}/internal/handoffs",
                json={"user_key": user_key, "reason": reason, "channel": channel},
                headers=self._headers,
            )
            response.raise_for_status()
            return response.json()
