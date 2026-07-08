from __future__ import annotations

from admin_service.shared.audit_repository import AdminAuditEvent


def audit_event_to_dict(event: AdminAuditEvent) -> dict[str, object]:
    return {
        "id": event.id,
        "actor": event.actor,
        "action": event.action,
        "target": event.target,
        "outcome": event.outcome,
        "detail": event.detail,
        "created_at": event.created_at,
    }
