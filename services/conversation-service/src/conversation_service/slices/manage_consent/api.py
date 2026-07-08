from __future__ import annotations

from fastapi import APIRouter, Depends, Query

from civi_common import require_internal_token

from .schemas import ConsentResponse, UpdateConsentRequest
from .use_case import get_consent, update_consent

router = APIRouter(tags=["conversations"])


@router.post(
    "/internal/conversations/consent",
    response_model=ConsentResponse,
    dependencies=[Depends(require_internal_token)],
)
async def post_consent(payload: UpdateConsentRequest) -> ConsentResponse:
    return await update_consent(payload)


@router.get(
    "/internal/conversations/consent",
    response_model=ConsentResponse,
    dependencies=[Depends(require_internal_token)],
)
async def read_consent(
    user_key: str = Query(min_length=1),
    channel: str = Query(default="web", min_length=1),
) -> ConsentResponse:
    return await get_consent(user_key=user_key, channel=channel)
