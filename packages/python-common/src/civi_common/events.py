from __future__ import annotations

import json
import os
from collections.abc import Mapping
from datetime import UTC, datetime
from typing import Any, Protocol
from uuid import uuid4


class EventPublisher(Protocol):
    async def publish(
        self,
        event_type: str,
        data: Mapping[str, Any],
        *,
        producer: str,
        correlation_id: str | None = None,
    ) -> None:
        ...


def build_event(
    event_type: str,
    data: Mapping[str, Any],
    *,
    producer: str,
    correlation_id: str | None = None,
) -> dict[str, Any]:
    if not event_type.strip():
        raise ValueError("event_type is required")
    if not producer.strip():
        raise ValueError("producer is required")
    event = dict(data)
    event.update({
        "event_id": str(uuid4()),
        "event_type": event_type,
        "schema_version": "1",
        "occurred_at": datetime.now(UTC).isoformat(timespec="seconds"),
        "producer": producer,
    })
    if correlation_id:
        event["correlation_id"] = correlation_id
    return event


class DisabledEventPublisher:
    async def publish(
        self,
        event_type: str,
        data: Mapping[str, Any],
        *,
        producer: str,
        correlation_id: str | None = None,
    ) -> None:
        return None


class InMemoryEventPublisher:
    def __init__(self) -> None:
        self.events: list[dict[str, Any]] = []

    async def publish(
        self,
        event_type: str,
        data: Mapping[str, Any],
        *,
        producer: str,
        correlation_id: str | None = None,
    ) -> None:
        self.events.append(
            build_event(
                event_type,
                data,
                producer=producer,
                correlation_id=correlation_id,
            )
        )


class RedisEventPublisher:
    def __init__(self, redis_url: str, *, channel_prefix: str = "civi.events") -> None:
        if not redis_url.strip():
            raise ValueError("redis_url is required")
        self._redis_url = redis_url
        self._channel_prefix = channel_prefix.strip().strip(".") or "civi.events"
        self._client: Any | None = None

    async def publish(
        self,
        event_type: str,
        data: Mapping[str, Any],
        *,
        producer: str,
        correlation_id: str | None = None,
    ) -> None:
        event = build_event(
            event_type,
            data,
            producer=producer,
            correlation_id=correlation_id,
        )
        client = self._client
        if client is None:
            from redis import asyncio as redis_asyncio

            client = redis_asyncio.from_url(self._redis_url, encoding="utf-8", decode_responses=True)
            self._client = client
        channel = f"{self._channel_prefix}.{event_type}"
        await client.publish(channel, json.dumps(event, sort_keys=True, separators=(",", ":")))


def event_publisher_from_env() -> EventPublisher:
    mode = os.getenv("EVENT_PUBLISHER_MODE", "disabled").strip().lower()
    if mode in {"", "disabled", "off"}:
        return DisabledEventPublisher()
    if mode == "redis":
        redis_url = os.getenv("EVENT_REDIS_URL", os.getenv("REDIS_URL", "redis://localhost:6379/1")).strip()
        channel_prefix = os.getenv("EVENT_CHANNEL_PREFIX", "civi.events")
        return RedisEventPublisher(redis_url, channel_prefix=channel_prefix)
    raise RuntimeError(f"unsupported event publisher mode: {mode}")
