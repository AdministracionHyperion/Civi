from __future__ import annotations

from fastapi import APIRouter, Depends

from admin_service.shared.audit_repository import repository as audit_repository
from admin_service.shared.auth import require_admin_basic

from .schemas import AuthenticateAdminResponse

router = APIRouter(tags=["admin"])


@router.post(
    "/internal/admin/auth/check",
    response_model=AuthenticateAdminResponse,
)
async def post_auth_check(admin_user: str = Depends(require_admin_basic)) -> AuthenticateAdminResponse:
    audit_repository.record(
        actor=admin_user,
        action="admin.auth.check",
        target="admin.auth",
    )
    return AuthenticateAdminResponse()
