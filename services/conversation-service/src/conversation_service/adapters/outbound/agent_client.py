from __future__ import annotations

import os
from typing import Any, Protocol

import httpx

from conversation_service.slices.run_turn.schemas import RunTurnRequest


class AgentClient(Protocol):
    async def run_turn(self, payload: RunTurnRequest) -> dict[str, Any]:
        ...


class HttpAgentClient:
    def __init__(self, *, base_url: str | None = None, token: str | None = None) -> None:
        self.base_url = (base_url or os.getenv("BOT_ORCHESTRATOR_URL", "http://localhost:8082")).rstrip("/")
        self.token = (token if token is not None else os.getenv("INTERNAL_SERVICE_TOKEN", "")).strip()
        if not self.token:
            raise RuntimeError("INTERNAL_SERVICE_TOKEN is required")

    async def run_turn(self, payload: RunTurnRequest) -> dict[str, Any]:
        async with httpx.AsyncClient(timeout=60.0) as client:
            response = await client.post(
                f"{self.base_url}/internal/agent/turns",
                json=payload.model_dump(),
                headers={"Authorization": f"Bearer {self.token}"},
            )
            response.raise_for_status()
            return response.json()
