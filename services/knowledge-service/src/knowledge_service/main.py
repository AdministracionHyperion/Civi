from __future__ import annotations

from fastapi import Depends, FastAPI

from civi_common import health_payload, require_internal_token
from knowledge_service.slices.get_city_info.api import router as city_router
from knowledge_service.slices.get_domain_info.api import router as domain_router
from knowledge_service.slices.search_knowledge.api import router as search_router

SERVICE_NAME = "knowledge-service"

app = FastAPI(title="Civi Knowledge Service", version="0.1.0")
app.include_router(domain_router)
app.include_router(city_router)
app.include_router(search_router)


@app.get("/health/live")
async def live() -> dict[str, str]:
    return health_payload(SERVICE_NAME)


@app.get("/health/ready")
async def ready() -> dict[str, str]:
    return health_payload(SERVICE_NAME)


@app.get("/internal/status", dependencies=[Depends(require_internal_token)])
async def internal_status() -> dict[str, str]:
    return health_payload(SERVICE_NAME)
