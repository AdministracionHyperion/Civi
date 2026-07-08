from __future__ import annotations

import os
from typing import Protocol

import httpx
from civi_common.events import EventPublisher, event_publisher_from_env

from .schemas import ReceiveMessageRequest, ReceiveMessageResponse


class ConversationClient(Protocol):
    async def run_turn(self, payload: ReceiveMessageRequest) -> dict[str, object]:
        ...


class HttpConversationClient:
    async def run_turn(self, payload: ReceiveMessageRequest) -> dict[str, object]:
        base_url = os.getenv("CONVERSATION_SERVICE_URL", "http://localhost:8081").rstrip("/")
        token = os.getenv("INTERNAL_SERVICE_TOKEN", "").strip()
        if not token:
            raise RuntimeError("INTERNAL_SERVICE_TOKEN is required")

        async with httpx.AsyncClient(timeout=30.0) as client:
            response = await client.post(
                f"{base_url}/internal/conversations/turns",
                json=payload.model_dump(),
                headers={"Authorization": f"Bearer {token}"},
            )
            response.raise_for_status()
            return response.json()


async def receive_message(
    payload: ReceiveMessageRequest,
    *,
    conversation_client: ConversationClient | None = None,
    event_publisher: EventPublisher | None = None,
) -> ReceiveMessageResponse:
    publisher = event_publisher or event_publisher_from_env()
    await publisher.publish(
        "message.received",
        {
            "user_key": payload.user_key,
            "channel": payload.channel,
            "text": payload.text,
            "has_location": _has_location_metadata(payload.metadata),
        },
        producer="channel-gateway",
    )

    data = await (conversation_client or HttpConversationClient()).run_turn(payload)

    return ReceiveMessageResponse(
        user_key=data["user_key"],
        text=data["text"],
        source="conversation-service",
    )


def _has_location_metadata(metadata: dict[str, object]) -> bool:
    return any(
        key in metadata
        for key in (
            "location_lat",
            "location_lng",
            "geo_lat",
            "geo_lng",
        )
    )
