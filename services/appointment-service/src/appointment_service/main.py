from __future__ import annotations

from fastapi import Depends, FastAPI

from civi_common import health_payload, require_internal_token
from appointment_service.slices.cancel_appointment.api import router as cancel_router
from appointment_service.slices.create_appointment.api import router as create_router
from appointment_service.slices.list_appointments.api import router as list_router

SERVICE_NAME = "appointment-service"

app = FastAPI(title="Civi Appointment Service", version="0.1.0")
app.include_router(create_router)
app.include_router(list_router)
app.include_router(cancel_router)


@app.get("/health/live")
async def live() -> dict[str, str]:
    return health_payload(SERVICE_NAME)


@app.get("/health/ready")
async def ready() -> dict[str, str]:
    return health_payload(SERVICE_NAME)


@app.get("/internal/status", dependencies=[Depends(require_internal_token)])
async def internal_status() -> dict[str, str]:
    return health_payload(SERVICE_NAME)
