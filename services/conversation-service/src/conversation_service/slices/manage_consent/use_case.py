from __future__ import annotations

from civi_common.events import EventPublisher, event_publisher_from_env
from conversation_service.shared.repository import ConversationRepository, repository

from .schemas import ConsentResponse, UpdateConsentRequest


async def update_consent(
    payload: UpdateConsentRequest,
    *,
    conversation_repository: ConversationRepository | None = None,
    event_publisher: EventPublisher | None = None,
) -> ConsentResponse:
    record = (conversation_repository or repository).set_consent(
        user_key=payload.user_key,
        channel=payload.channel,
        status=payload.status,
        purpose=payload.purpose,
        policy_version=payload.policy_version,
    )
    await (event_publisher or event_publisher_from_env()).publish(
        "consent.updated",
        {
            "user_key": record.user_key,
            "channel": record.channel,
            "status": record.status,
            "purpose": record.purpose,
            "policy_version": record.policy_version,
        },
        producer="conversation-service",
    )
    return ConsentResponse(
        user_key=record.user_key,
        channel=record.channel,
        status=record.status,
        purpose=record.purpose,
        policy_version=record.policy_version,
        updated_at=record.updated_at,
    )


async def get_consent(
    *,
    user_key: str,
    channel: str = "web",
    conversation_repository: ConversationRepository | None = None,
) -> ConsentResponse:
    record = (conversation_repository or repository).get_consent(user_key=user_key, channel=channel)
    if record is None:
        return ConsentResponse(
            user_key=user_key,
            channel=channel,
            status="unknown",
            purpose="civi_conversation",
            policy_version="unknown",
            updated_at=None,
        )
    return ConsentResponse(
        user_key=record.user_key,
        channel=record.channel,
        status=record.status,
        purpose=record.purpose,
        policy_version=record.policy_version,
        updated_at=record.updated_at,
    )
