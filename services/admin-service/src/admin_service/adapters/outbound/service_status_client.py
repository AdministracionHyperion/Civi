from __future__ import annotations

import os
from typing import Any, Protocol

import httpx

SERVICE_URL_ENV = {
    "channel-gateway": "CHANNEL_GATEWAY_URL",
    "conversation-service": "CONVERSATION_SERVICE_URL",
    "bot-orchestrator": "BOT_ORCHESTRATOR_URL",
    "vehicle-service": "VEHICLE_SERVICE_URL",
    "runt-service": "RUNT_SERVICE_URL",
    "simit-service": "SIMIT_SERVICE_URL",
    "places-service": "PLACES_SERVICE_URL",
    "appointment-service": "APPOINTMENT_SERVICE_URL",
    "notification-service": "NOTIFICATION_SERVICE_URL",
    "media-service": "MEDIA_SERVICE_URL",
    "knowledge-service": "KNOWLEDGE_SERVICE_URL",
    "quote-service": "QUOTE_SERVICE_URL",
    "billing-service": "BILLING_SERVICE_URL",
    "handoff-service": "HANDOFF_SERVICE_URL",
}

DEFAULT_SERVICE_URLS = {
    "channel-gateway": "http://localhost:8080",
    "conversation-service": "http://localhost:8081",
    "bot-orchestrator": "http://localhost:8082",
    "vehicle-service": "http://localhost:8083",
    "runt-service": "http://localhost:8084",
    "simit-service": "http://localhost:8090",
    "places-service": "http://localhost:8085",
    "appointment-service": "http://localhost:8086",
    "notification-service": "http://localhost:8087",
    "media-service": "http://localhost:8088",
    "knowledge-service": "http://localhost:8094",
    "quote-service": "http://localhost:8091",
    "billing-service": "http://localhost:8092",
    "handoff-service": "http://localhost:8093",
}


class StatusClient(Protocol):
    async def fetch_statuses(self) -> list[dict[str, object]]:
        ...


class InternalServiceStatusClient:
    def __init__(
        self,
        *,
        token: str | None = None,
        service_urls: dict[str, str] | None = None,
        timeout_seconds: float = 5.0,
    ) -> None:
        self.token = (token if token is not None else os.getenv("INTERNAL_SERVICE_TOKEN", "")).strip()
        if not self.token:
            raise RuntimeError("INTERNAL_SERVICE_TOKEN is required for admin service status checks")
        self.service_urls = service_urls or service_urls_from_env()
        self.timeout_seconds = timeout_seconds

    async def fetch_statuses(self) -> list[dict[str, object]]:
        statuses = []
        async with httpx.AsyncClient(timeout=self.timeout_seconds) as client:
            for service, base_url in self.service_urls.items():
                statuses.append(await self._fetch_one(client, service=service, base_url=base_url))
        return statuses

    async def _fetch_one(self, client: httpx.AsyncClient, *, service: str, base_url: str) -> dict[str, object]:
        try:
            response = await client.get(
                f"{base_url.rstrip('/')}/internal/status",
                headers={"Authorization": f"Bearer {self.token}"},
            )
            response.raise_for_status()
            data: dict[str, Any] = response.json()
            return {
                "service": service,
                "status": data.get("status", "unknown"),
                "reported_service": data.get("service"),
            }
        except Exception as exc:
            return {
                "service": service,
                "status": "degraded",
                "error": exc.__class__.__name__,
            }


def service_urls_from_env() -> dict[str, str]:
    return {
        service: os.getenv(env_name, DEFAULT_SERVICE_URLS[service]).rstrip("/")
        for service, env_name in SERVICE_URL_ENV.items()
    }
