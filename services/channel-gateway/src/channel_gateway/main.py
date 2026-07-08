from __future__ import annotations

import os

from fastapi import Depends, FastAPI
from fastapi.middleware.cors import CORSMiddleware

from civi_common import health_payload, require_internal_token
from channel_gateway.slices.receive_message.api import router as receive_message_router
from channel_gateway.slices.receive_whatsapp_webhook.api import router as whatsapp_webhook_router

SERVICE_NAME = "channel-gateway"

app = FastAPI(title="Civi Channel Gateway", version="0.1.0")
_cors_origins = [origin.strip() for origin in os.getenv("CHANNEL_CORS_ALLOWED_ORIGINS", "").split(",") if origin.strip()]
if _cors_origins:
    app.add_middleware(
        CORSMiddleware,
        allow_origins=_cors_origins,
        allow_credentials=False,
        allow_methods=["POST", "GET", "OPTIONS"],
        allow_headers=["Content-Type", "X-Hub-Signature-256"],
    )
app.include_router(receive_message_router)
app.include_router(whatsapp_webhook_router)


@app.get("/health/live")
async def live() -> dict[str, str]:
    return health_payload(SERVICE_NAME)


@app.get("/health/ready")
async def ready() -> dict[str, str]:
    return health_payload(SERVICE_NAME)


@app.get("/internal/status", dependencies=[Depends(require_internal_token)])
async def internal_status() -> dict[str, str]:
    return health_payload(SERVICE_NAME)
