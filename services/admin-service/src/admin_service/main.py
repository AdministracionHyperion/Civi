from __future__ import annotations

from fastapi import Depends, FastAPI

from civi_common import health_payload, require_internal_token
from admin_service.slices.authenticate_admin.api import router as auth_router
from admin_service.slices.consume_internal_event.api import router as event_router
from admin_service.slices.list_audit_events.api import router as audit_router
from admin_service.slices.list_dashboard_citas.api import router as dashboard_router
from admin_service.slices.manage_partners.api import router as partners_router

SERVICE_NAME = "admin-service"

app = FastAPI(title="Civi Admin Service", version="0.1.0")
app.include_router(auth_router)
app.include_router(dashboard_router)
app.include_router(partners_router)
app.include_router(audit_router)
app.include_router(event_router)


@app.get("/health/live")
async def live() -> dict[str, str]:
    return health_payload(SERVICE_NAME)


@app.get("/health/ready")
async def ready() -> dict[str, str]:
    return health_payload(SERVICE_NAME)


@app.get("/internal/status", dependencies=[Depends(require_internal_token)])
async def internal_status() -> dict[str, str]:
    return health_payload(SERVICE_NAME)
