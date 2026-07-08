from __future__ import annotations

from fastapi import Depends, FastAPI

from civi_common import health_payload, require_internal_token
from quote_service.slices.create_quote.api import router as quote_router

SERVICE_NAME = "quote-service"

app = FastAPI(title="Civi Quote Service", version="0.1.0")
app.include_router(quote_router)


@app.get("/health/live")
async def live() -> dict[str, str]:
    return health_payload(SERVICE_NAME)


@app.get("/health/ready")
async def ready() -> dict[str, str]:
    return health_payload(SERVICE_NAME)


@app.get("/internal/status", dependencies=[Depends(require_internal_token)])
async def internal_status() -> dict[str, str]:
    return health_payload(SERVICE_NAME)
