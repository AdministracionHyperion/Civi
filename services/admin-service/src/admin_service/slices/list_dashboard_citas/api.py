from __future__ import annotations

from fastapi import APIRouter, Depends

from admin_service.shared.audit_repository import repository as audit_repository
from admin_service.shared.auth import require_admin_basic

from .schemas import DashboardSummaryResponse
from .use_case import dashboard_summary

router = APIRouter(tags=["admin"])


@router.get(
    "/internal/admin/dashboard/summary",
    response_model=DashboardSummaryResponse,
)
async def get_dashboard_summary(admin_user: str = Depends(require_admin_basic)) -> DashboardSummaryResponse:
    audit_repository.record(
        actor=admin_user,
        action="admin.dashboard.summary",
        target="admin.dashboard",
    )
    return await dashboard_summary()
