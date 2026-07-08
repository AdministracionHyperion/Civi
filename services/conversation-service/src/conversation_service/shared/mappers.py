from __future__ import annotations

from conversation_service.shared.repository import ConversationConsentRecord, ConversationTurnRecord


def conversation_turn_to_dict(record: ConversationTurnRecord) -> dict[str, object]:
    return {
        "id": record.id,
        "user_key": record.user_key,
        "channel": record.channel,
        "user_text": record.user_text,
        "agent_text": record.agent_text,
        "state_version": record.state_version,
        "created_at": record.created_at,
    }


def consent_to_dict(record: ConversationConsentRecord) -> dict[str, object]:
    return {
        "user_key": record.user_key,
        "channel": record.channel,
        "status": record.status,
        "purpose": record.purpose,
        "policy_version": record.policy_version,
        "updated_at": record.updated_at,
    }
