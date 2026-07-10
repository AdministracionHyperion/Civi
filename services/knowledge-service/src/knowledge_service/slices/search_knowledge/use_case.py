from __future__ import annotations

from knowledge_service.shared.search import search_corpus

from .schemas import KnowledgeHit, SearchKnowledgeRequest, SearchKnowledgeResponse


async def search_knowledge(payload: SearchKnowledgeRequest) -> SearchKnowledgeResponse:
    hits = search_corpus(query=payload.query, domain=payload.domain, limit=payload.limit)
    if not hits:
        return SearchKnowledgeResponse(
            success=False,
            hits=[],
            message="No encontre contexto validado suficiente para esa consulta.",
        )
    return SearchKnowledgeResponse(
        success=True,
        hits=[
            KnowledgeHit(
                id=hit.id,
                title=hit.title,
                body=hit.body,
                domain=hit.domain,
                score=hit.score,
            )
            for hit in hits
        ],
    )
