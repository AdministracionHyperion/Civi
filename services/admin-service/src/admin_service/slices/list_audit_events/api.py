from __future__ import annotations

from fastapi import APIRouter, Depends, Query

from admin_service.shared.audit_repository import repository as audit_repository
from admin_service.shared.auth import require_admin_basic

from .schemas import ListAuditEventsResponse
from .use_case import list_audit_events

router = APIRouter(tags=["admin"])


@router.get(
    "/internal/admin/audit",
    response_model=ListAuditEventsResponse,
)
async def get_audit_events(
    admin_user: str = Depends(require_admin_basic),
    limit: int = Query(default=100, ge=1, le=500),
) -> ListAuditEventsResponse:
    audit_repository.record(
        actor=admin_user,
        action="admin.audit.list",
        target="admin.audit",
    )
    return await list_audit_events(limit=limit)
