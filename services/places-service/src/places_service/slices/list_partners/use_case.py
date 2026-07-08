from __future__ import annotations

from places_service.shared.repository import PlacesRepository, repository

from .schemas import ListPartnersResponse, PartnerSummary


async def list_partners(*, places_repository: PlacesRepository | None = None) -> ListPartnersResponse:
    return ListPartnersResponse(
        partners=[
            PartnerSummary(
                id=place.id,
                name=place.name,
                city=place.city,
                department=place.department,
                kind=place.kind,
            )
            for place in (places_repository or repository).list_partners()
        ]
    )
