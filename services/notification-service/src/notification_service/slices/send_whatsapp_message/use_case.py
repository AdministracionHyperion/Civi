from __future__ import annotations

from civi_common.events import EventPublisher, event_publisher_from_env
from notification_service.shared.mappers import outbox_to_dict
from notification_service.shared.repository import repository

from .schemas import SendWhatsAppMessageRequest, SendWhatsAppMessageResponse


async def send_whatsapp_message(
    payload: SendWhatsAppMessageRequest,
    *,
    event_publisher: EventPublisher | None = None,
) -> SendWhatsAppMessageResponse:
    message = repository.queue_message(to=payload.to, body=payload.body, channel="whatsapp")
    serialized = outbox_to_dict(message)
    await (event_publisher or event_publisher_from_env()).publish(
        "notification.queued",
        {
            "message_id": message.id,
            "channel": message.channel,
            "to_tail": serialized["to_tail"],
        },
        producer="notification-service",
    )
    return SendWhatsAppMessageResponse(message=serialized)
