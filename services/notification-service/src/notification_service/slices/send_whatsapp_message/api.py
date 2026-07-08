from __future__ import annotations

from fastapi import APIRouter, Depends

from civi_common import require_internal_token

from .schemas import SendWhatsAppMessageRequest, SendWhatsAppMessageResponse
from .use_case import send_whatsapp_message

router = APIRouter(tags=["notifications"])


@router.post(
    "/internal/notifications/whatsapp",
    response_model=SendWhatsAppMessageResponse,
    dependencies=[Depends(require_internal_token)],
    status_code=202,
)
async def post_whatsapp_message(payload: SendWhatsAppMessageRequest) -> SendWhatsAppMessageResponse:
    return await send_whatsapp_message(payload)
