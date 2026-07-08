from __future__ import annotations

from fastapi import Depends, FastAPI

from civi_common import health_payload, require_internal_token
from notification_service.slices.dispatch_outbox.api import router as dispatch_router
from notification_service.slices.process_due_reminders.api import router as due_reminders_router
from notification_service.slices.schedule_reminder.api import router as reminder_router
from notification_service.slices.send_whatsapp_message.api import router as whatsapp_router

SERVICE_NAME = "notification-service"

app = FastAPI(title="Civi Notification Service", version="0.1.0")
app.include_router(whatsapp_router)
app.include_router(reminder_router)
app.include_router(due_reminders_router)
app.include_router(dispatch_router)


@app.get("/health/live")
async def live() -> dict[str, str]:
    return health_payload(SERVICE_NAME)


@app.get("/health/ready")
async def ready() -> dict[str, str]:
    return health_payload(SERVICE_NAME)


@app.get("/internal/status", dependencies=[Depends(require_internal_token)])
async def internal_status() -> dict[str, str]:
    return health_payload(SERVICE_NAME)
