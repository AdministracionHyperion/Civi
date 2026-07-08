from __future__ import annotations

from fastapi import APIRouter, Depends

from channel_gateway.shared.rate_limit import require_public_rate_limit

from .schemas import ReceiveMessageRequest, ReceiveMessageResponse
from .use_case import receive_message

router = APIRouter(tags=["messages"])


@router.post(
    "/chat/messages",
    response_model=ReceiveMessageResponse,
    dependencies=[Depends(require_public_rate_limit)],
)
async def post_chat_message(payload: ReceiveMessageRequest) -> ReceiveMessageResponse:
    return await receive_message(payload)
