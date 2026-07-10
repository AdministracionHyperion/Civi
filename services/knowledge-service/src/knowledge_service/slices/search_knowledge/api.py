from __future__ import annotations

from fastapi import APIRouter, Depends

from civi_common import require_internal_token

from .schemas import SearchKnowledgeRequest, SearchKnowledgeResponse
from .use_case import search_knowledge

router = APIRouter(prefix="/internal/knowledge", dependencies=[Depends(require_internal_token)])


@router.post("/search", response_model=SearchKnowledgeResponse)
async def post_search_knowledge(payload: SearchKnowledgeRequest) -> SearchKnowledgeResponse:
    return await search_knowledge(payload)
