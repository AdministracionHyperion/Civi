from __future__ import annotations

import os
from typing import Protocol

import httpx


class WhatsAppProvider(Protocol):
    async def send(self, *, to: str, body: str) -> dict[str, object]:
        ...


class DisabledWhatsAppProvider:
    async def send(self, *, to: str, body: str) -> dict[str, object]:
        return {
            "status": "disabled_until_provider_configured",
            "provider": "whatsapp",
        }


class MetaWhatsAppProvider:
    def __init__(
        self,
        *,
        access_token: str,
        phone_number_id: str,
        api_version: str = "v20.0",
        base_url: str = "https://graph.facebook.com",
        transport: httpx.AsyncBaseTransport | None = None,
    ) -> None:
        self.access_token = access_token.strip()
        self.phone_number_id = phone_number_id.strip()
        self.api_version = api_version.strip().strip("/")
        self.base_url = base_url.rstrip("/")
        self.transport = transport
        if not self.access_token or not self.phone_number_id:
            raise RuntimeError("WHATSAPP_ACCESS_TOKEN and WHATSAPP_PHONE_NUMBER_ID are required")

    async def send(self, *, to: str, body: str) -> dict[str, object]:
        payload = {
            "messaging_product": "whatsapp",
            "recipient_type": "individual",
            "to": to,
            "type": "text",
            "text": {"preview_url": False, "body": body},
        }
        async with httpx.AsyncClient(timeout=20.0, transport=self.transport) as client:
            response = await client.post(
                f"{self.base_url}/{self.api_version}/{self.phone_number_id}/messages",
                json=payload,
                headers={"Authorization": f"Bearer {self.access_token}"},
            )
            response.raise_for_status()
            data = response.json()
        return {
            "status": "sent",
            "provider": "meta-whatsapp",
            "provider_message_id": _extract_message_id(data),
        }


def whatsapp_provider_from_env() -> WhatsAppProvider:
    mode = os.getenv("WHATSAPP_PROVIDER_MODE", "disabled").strip().lower()
    if mode in {"", "disabled"}:
        return DisabledWhatsAppProvider()
    if mode == "meta":
        return MetaWhatsAppProvider(
            access_token=os.getenv("WHATSAPP_ACCESS_TOKEN", ""),
            phone_number_id=os.getenv("WHATSAPP_PHONE_NUMBER_ID", ""),
            api_version=os.getenv("WHATSAPP_GRAPH_API_VERSION", "v20.0"),
        )
    raise RuntimeError(f"unsupported WhatsApp provider mode: {mode}")


def _extract_message_id(data: dict[str, object]) -> str | None:
    messages = data.get("messages")
    if not isinstance(messages, list) or not messages:
        return None
    first = messages[0]
    if not isinstance(first, dict):
        return None
    message_id = first.get("id")
    return str(message_id) if message_id else None
