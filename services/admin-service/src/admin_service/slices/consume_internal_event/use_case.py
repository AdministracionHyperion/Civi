from __future__ import annotations

import json

from admin_service.shared.audit_repository import AdminAuditRepository, repository

from .schemas import ConsumeInternalEventRequest, ConsumeInternalEventResponse


async def consume_internal_event(
    payload: ConsumeInternalEventRequest,
    *,
    audit_repository: AdminAuditRepository | None = None,
) -> ConsumeInternalEventResponse:
    active_repository = audit_repository or repository
    record = active_repository.record(
        actor=payload.producer,
        action=f"event.{payload.event_type}",
        target=_target_for(payload),
        outcome="consumed",
        detail=_detail_for(payload),
    )
    return ConsumeInternalEventResponse(audit_event_id=record.id)


def _target_for(payload: ConsumeInternalEventRequest) -> str:
    if payload.appointment_id is not None:
        return f"appointment:{payload.appointment_id}"
    if payload.reminder_id is not None:
        return f"reminder:{payload.reminder_id}"
    if payload.message_id is not None:
        return f"notification:{payload.message_id}"
    if payload.user_key:
        return f"user_tail:{_tail(payload.user_key)}"
    return payload.event_type


def _detail_for(payload: ConsumeInternalEventRequest) -> str:
    detail: dict[str, object] = {
        "event_id": payload.event_id,
        "event_type": payload.event_type,
        "producer": payload.producer,
        "schema_version": payload.schema_version,
    }
    optional_fields: dict[str, object | None] = {
        "occurred_at": payload.occurred_at,
        "correlation_id": payload.correlation_id,
        "channel": payload.channel,
        "user_tail": _tail(payload.user_key) if payload.user_key else None,
        "appointment_id": payload.appointment_id,
        "reminder_id": payload.reminder_id,
        "message_id": payload.message_id,
        "status": payload.status,
        "provider": payload.provider,
        "to_tail": payload.to_tail,
    }
    detail.update({key: value for key, value in optional_fields.items() if value is not None})
    encoded = json.dumps(detail, sort_keys=True, separators=(",", ":"))
    return encoded[:1024]


def _tail(value: str, *, length: int = 4) -> str:
    stripped = value.strip()
    if len(stripped) <= length:
        return stripped
    return stripped[-length:]
