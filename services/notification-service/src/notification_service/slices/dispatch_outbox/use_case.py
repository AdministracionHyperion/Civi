from __future__ import annotations

from civi_common.events import EventPublisher, event_publisher_from_env
from notification_service.adapters.outbound.whatsapp_provider import (
    WhatsAppProvider,
    whatsapp_provider_from_env,
)
from notification_service.shared.mappers import outbox_to_dict
from notification_service.shared.repository import repository

from .schemas import DispatchOutboxResponse


async def dispatch_outbox(
    *,
    limit: int = 50,
    provider: WhatsAppProvider | None = None,
    event_publisher: EventPublisher | None = None,
) -> DispatchOutboxResponse:
    active_provider = provider or whatsapp_provider_from_env()
    publisher = event_publisher or event_publisher_from_env()
    dispatched = []
    for message in repository.list_queued(limit=limit):
        provider_result = await active_provider.send(to=message.to, body=message.body)
        item = outbox_to_dict(message)
        item["dispatch_status"] = provider_result.get("status", "unknown")
        item["provider"] = provider_result.get("provider", message.channel)
        if provider_result.get("status") == "sent":
            sent = repository.mark_sent(message.id)
            if sent is not None:
                item = outbox_to_dict(sent)
                item["dispatch_status"] = "sent"
                item["provider"] = provider_result.get("provider", message.channel)
                await publisher.publish(
                    "notification.sent",
                    {
                        "message_id": sent.id,
                        "channel": sent.channel,
                        "provider": item["provider"],
                        "provider_message_id": provider_result.get("provider_message_id"),
                    },
                    producer="notification-service",
                )
        dispatched.append(item)
    return DispatchOutboxResponse(dispatched=dispatched)
