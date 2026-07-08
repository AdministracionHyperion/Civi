from __future__ import annotations

from fastapi import APIRouter, Depends

from admin_service.shared.audit_repository import repository as audit_repository
from admin_service.shared.auth import require_admin_basic

from .schemas import ManagePartnersResponse

router = APIRouter(tags=["admin"])


@router.get(
    "/internal/admin/partners",
    response_model=ManagePartnersResponse,
)
async def get_partner_management(admin_user: str = Depends(require_admin_basic)) -> ManagePartnersResponse:
    audit_repository.record(
        actor=admin_user,
        action="admin.partners.list",
        target="admin.partners",
    )
    return ManagePartnersResponse()
