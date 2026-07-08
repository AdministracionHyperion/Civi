from __future__ import annotations

from fastapi import Depends, FastAPI

from civi_common import health_payload, require_internal_token
from media_service.slices.process_audio.api import router as audio_router
from media_service.slices.process_image.api import router as image_router
from media_service.slices.validate_media.api import router as validate_router

SERVICE_NAME = "media-service"

app = FastAPI(title="Civi Media Service", version="0.1.0")
app.include_router(validate_router)
app.include_router(audio_router)
app.include_router(image_router)


@app.get("/health/live")
async def live() -> dict[str, str]:
    return health_payload(SERVICE_NAME)


@app.get("/health/ready")
async def ready() -> dict[str, str]:
    return health_payload(SERVICE_NAME)


@app.get("/internal/status", dependencies=[Depends(require_internal_token)])
async def internal_status() -> dict[str, str]:
    return health_payload(SERVICE_NAME)
