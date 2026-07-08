from __future__ import annotations

from fastapi import Depends, FastAPI

from civi_common import health_payload, require_internal_token
from vehicle_service.slices.check_vigencia.api import router as check_vigencia_router
from vehicle_service.slices.consult_multas.api import router as consult_multas_router
from vehicle_service.slices.consult_runt_profile.api import router as consult_runt_profile_router

SERVICE_NAME = "vehicle-service"

app = FastAPI(title="Civi Vehicle Service", version="0.1.0")
app.include_router(check_vigencia_router)
app.include_router(consult_multas_router)
app.include_router(consult_runt_profile_router)


@app.get("/health/live")
async def live() -> dict[str, str]:
    return health_payload(SERVICE_NAME)


@app.get("/health/ready")
async def ready() -> dict[str, str]:
    return health_payload(SERVICE_NAME)


@app.get("/internal/status", dependencies=[Depends(require_internal_token)])
async def internal_status() -> dict[str, str]:
    return health_payload(SERVICE_NAME)
