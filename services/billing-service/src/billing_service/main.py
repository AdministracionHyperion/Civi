from __future__ import annotations

from fastapi import Depends, FastAPI

from billing_service.slices.create_payment_intent.api import router as payment_router
from civi_common import health_payload, require_internal_token

SERVICE_NAME = "billing-service"

app = FastAPI(title="Civi Billing Service", version="0.1.0")
app.include_router(payment_router)


@app.get("/health/live")
async def live() -> dict[str, str]:
    return health_payload(SERVICE_NAME)


@app.get("/health/ready")
async def ready() -> dict[str, str]:
    return health_payload(SERVICE_NAME)


@app.get("/internal/status", dependencies=[Depends(require_internal_token)])
async def internal_status() -> dict[str, str]:
    return health_payload(SERVICE_NAME)
