from __future__ import annotations

from fastapi import Depends, FastAPI

from civi_common import health_payload, require_internal_token
from conversation_service.slices.list_history.api import router as history_router
from conversation_service.slices.manage_consent.api import router as consent_router
from conversation_service.slices.run_turn.api import router as run_turn_router

SERVICE_NAME = "conversation-service"

app = FastAPI(title="Civi Conversation Service", version="0.1.0")
app.include_router(run_turn_router)
app.include_router(history_router)
app.include_router(consent_router)


@app.get("/health/live")
async def live() -> dict[str, str]:
    return health_payload(SERVICE_NAME)


@app.get("/health/ready")
async def ready() -> dict[str, str]:
    return health_payload(SERVICE_NAME)


@app.get("/internal/status", dependencies=[Depends(require_internal_token)])
async def internal_status() -> dict[str, str]:
    return health_payload(SERVICE_NAME)
