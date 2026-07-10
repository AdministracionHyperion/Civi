from __future__ import annotations

from pathlib import Path

from fastapi import Depends, FastAPI
from fastapi.staticfiles import StaticFiles

from civi_common import health_payload, require_internal_token
from places_service.slices.booking_eligibility.api import router as eligibility_router
from places_service.slices.catalog_summary.api import router as summary_router
from places_service.slices.find_nearest_place.api import router as nearest_router
from places_service.slices.get_place.api import router as get_place_router
from places_service.slices.list_partners.api import router as partners_router
from places_service.slices.places_geojson.api import router as geojson_router

SERVICE_NAME = "places-service"

app = FastAPI(title="Civi Places Service", version="0.2.0")
# Static paths before parameterized {site_id}
app.include_router(nearest_router)
app.include_router(partners_router)
app.include_router(summary_router)
app.include_router(eligibility_router)
app.include_router(geojson_router)
app.include_router(get_place_router)

_STATIC_DIR = Path(__file__).resolve().parents[2] / "static"
if _STATIC_DIR.is_dir():
    app.mount("/static", StaticFiles(directory=str(_STATIC_DIR)), name="static")


@app.get("/health/live")
async def live() -> dict[str, str]:
    return health_payload(SERVICE_NAME)


@app.get("/health/ready")
async def ready() -> dict[str, str]:
    return health_payload(SERVICE_NAME)


@app.get("/internal/status", dependencies=[Depends(require_internal_token)])
async def internal_status() -> dict[str, str]:
    return health_payload(SERVICE_NAME)
