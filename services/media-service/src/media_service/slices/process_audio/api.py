from __future__ import annotations

from fastapi import APIRouter, Depends

from civi_common import require_internal_token

from .schemas import ProcessAudioRequest, ProcessAudioResponse
from .use_case import process_audio

router = APIRouter(tags=["media"])


@router.post(
    "/internal/media/audio",
    response_model=ProcessAudioResponse,
    dependencies=[Depends(require_internal_token)],
)
async def post_audio(payload: ProcessAudioRequest) -> ProcessAudioResponse:
    return await process_audio(payload)
