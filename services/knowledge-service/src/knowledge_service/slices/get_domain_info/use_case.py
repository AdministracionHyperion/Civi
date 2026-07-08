from __future__ import annotations

from knowledge_service.shared.knowledge_base import available_topics, get_item, normalize_domain, normalize_key

from .schemas import GetDomainInfoRequest, GetDomainInfoResponse


async def get_domain_info(payload: GetDomainInfoRequest) -> GetDomainInfoResponse:
    domain = normalize_domain(payload.domain)
    if domain is None:
        return GetDomainInfoResponse(
            success=False,
            domain=normalize_key(payload.domain),
            topic=normalize_key(payload.topic),
            message="Dominio no soportado.",
        )

    topic = normalize_key(payload.topic)
    item = get_item(domain, topic)
    topics = available_topics(domain)
    if item is None:
        return GetDomainInfoResponse(
            success=False,
            domain=domain,
            topic=topic,
            available_topics=topics,
            message="Tema no soportado para ese dominio.",
        )

    return GetDomainInfoResponse(
        success=True,
        domain=domain,
        topic=item.topic,
        title=item.title,
        body=item.body,
        available_topics=topics,
    )
