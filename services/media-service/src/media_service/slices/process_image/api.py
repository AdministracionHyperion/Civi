from __future__ import annotations

from fastapi import APIRouter, Depends

from civi_common import require_internal_token

from .schemas import ProcessImageRequest, ProcessImageResponse
from .use_case import process_image

router = APIRouter(tags=["media"])


@router.post(
    "/internal/media/image",
    response_model=ProcessImageResponse,
    dependencies=[Depends(require_internal_token)],
)
async def post_image(payload: ProcessImageRequest) -> ProcessImageResponse:
    return await process_image(payload)
