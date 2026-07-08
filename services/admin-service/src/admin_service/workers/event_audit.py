from __future__ import annotations

import asyncio
import json
import logging
import os
from typing import Any

from admin_service.shared.audit_repository import AdminAuditRepository
from admin_service.slices.consume_internal_event.schemas import ConsumeInternalEventRequest
from admin_service.slices.consume_internal_event.use_case import consume_internal_event

logger = logging.getLogger("admin_service.workers.event_audit")


async def consume_raw_event(
    raw_event: str | bytes,
    *,
    audit_repository: AdminAuditRepository | None = None,
) -> int | None:
    try:
        decoded = raw_event.decode("utf-8") if isinstance(raw_event, bytes) else raw_event
        payload = json.loads(decoded)
        request = ConsumeInternalEventRequest(**payload)
        response = await consume_internal_event(request, audit_repository=audit_repository)
        return response.audit_event_id
    except Exception:
        logger.exception("admin event audit worker could not consume event")
        return None


async def run_forever(
    *,
    redis_url: str | None = None,
    channel_prefix: str | None = None,
) -> None:
    active_redis_url = redis_url or os.getenv("EVENT_REDIS_URL", os.getenv("REDIS_URL", "redis://localhost:6379/1"))
    active_prefix = (channel_prefix or os.getenv("EVENT_CHANNEL_PREFIX", "civi.events")).strip().strip(".")
    pattern = f"{active_prefix or 'civi.events'}.*"

    from redis import asyncio as redis_asyncio

    client = redis_asyncio.from_url(active_redis_url, encoding="utf-8", decode_responses=True)
    pubsub = client.pubsub()
    await pubsub.psubscribe(pattern)
    logger.info("admin event audit worker subscribed pattern=%s", pattern)
    try:
        async for message in pubsub.listen():
            if message.get("type") != "pmessage":
                continue
            await consume_raw_event(_message_data(message))
    finally:
        await pubsub.close()
        await client.aclose()


def main() -> None:
    logging.basicConfig(level=os.getenv("LOG_LEVEL", "INFO"))
    asyncio.run(run_forever())


def _message_data(message: dict[str, Any]) -> str | bytes:
    data = message.get("data", "")
    if isinstance(data, bytes):
        return data
    return str(data)


if __name__ == "__main__":
    main()
