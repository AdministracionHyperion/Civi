from __future__ import annotations

from admin_service.shared.audit_mappers import audit_event_to_dict
from admin_service.shared.audit_repository import AdminAuditRepository, repository

from .schemas import ListAuditEventsResponse


async def list_audit_events(
    *,
    limit: int = 100,
    audit_repository: AdminAuditRepository | None = None,
) -> ListAuditEventsResponse:
    records = (audit_repository or repository).list_events(limit=limit)
    return ListAuditEventsResponse(events=[audit_event_to_dict(record) for record in records])
