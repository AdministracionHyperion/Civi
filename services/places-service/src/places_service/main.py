from __future__ import annotations

from fastapi import Depends, FastAPI

from civi_common import health_payload, require_internal_token
from places_service.slices.find_nearest_place.api import router as nearest_router
from places_service.slices.list_partners.api import router as partners_router

SERVICE_NAME = "places-service"

app = FastAPI(title="Civi Places Service", version="0.1.0")
app.include_router(nearest_router)
app.include_router(partners_router)


@app.get("/health/live")
async def live() -> dict[str, str]:
    return health_payload(SERVICE_NAME)


@app.get("/health/ready")
async def ready() -> dict[str, str]:
    return health_payload(SERVICE_NAME)


@app.get("/internal/status", dependencies=[Depends(require_internal_token)])
async def internal_status() -> dict[str, str]:
    return health_payload(SERVICE_NAME)
