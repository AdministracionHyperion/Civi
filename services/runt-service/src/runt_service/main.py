from __future__ import annotations

from fastapi import Depends, FastAPI

from civi_common import health_payload, require_internal_token
from runt_service.slices.consult_persona.api import router as persona_router
from runt_service.slices.check_vigencia.api import router as vigencia_router
from runt_service.slices.list_document_types.api import router as document_types_router

SERVICE_NAME = "runt-service"

app = FastAPI(title="Civi RUNT Service", version="0.1.0")
app.include_router(vigencia_router)
app.include_router(persona_router)
app.include_router(document_types_router)


@app.get("/health/live")
async def live() -> dict[str, str]:
    return health_payload(SERVICE_NAME)


@app.get("/health/ready")
async def ready() -> dict[str, str]:
    return health_payload(SERVICE_NAME)


@app.get("/internal/status", dependencies=[Depends(require_internal_token)])
async def internal_status() -> dict[str, str]:
    return health_payload(SERVICE_NAME)
