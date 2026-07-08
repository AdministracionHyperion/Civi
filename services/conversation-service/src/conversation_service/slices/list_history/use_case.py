from __future__ import annotations

from conversation_service.shared.mappers import conversation_turn_to_dict
from conversation_service.shared.repository import ConversationRepository, repository

from .schemas import ListHistoryResponse


async def list_history(
    *,
    user_key: str,
    limit: int = 20,
    conversation_repository: ConversationRepository | None = None,
) -> ListHistoryResponse:
    records = (conversation_repository or repository).list_for_user(user_key=user_key, limit=limit)
    return ListHistoryResponse(turns=[conversation_turn_to_dict(record) for record in records])
