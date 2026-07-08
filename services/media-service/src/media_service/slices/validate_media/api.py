from __future__ import annotations

from fastapi import APIRouter, Depends

from civi_common import require_internal_token

from .schemas import ValidateMediaRequest, ValidateMediaResponse
from .use_case import validate_media

router = APIRouter(tags=["media"])


@router.post(
    "/internal/media/validate",
    response_model=ValidateMediaResponse,
    dependencies=[Depends(require_internal_token)],
)
async def post_validate(payload: ValidateMediaRequest) -> ValidateMediaResponse:
    return await validate_media(payload)
