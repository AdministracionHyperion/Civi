from __future__ import annotations

from fastapi import APIRouter, Depends

from civi_common import require_internal_token
from places_service.adapters.outbound.catalog_repository import catalog_repository_from_env

from .schemas import BookingEligibilityResponse

router = APIRouter(tags=["places"])


@router.get(
    "/internal/places/{site_id}/booking-eligibility",
    response_model=BookingEligibilityResponse,
    dependencies=[Depends(require_internal_token)],
)
async def booking_eligibility(site_id: str) -> BookingEligibilityResponse:
    repo = catalog_repository_from_env()
    if repo is None:
        return BookingEligibilityResponse(
            site_id=site_id,
            exists=False,
            is_partner=False,
            is_bookable=False,
            eligible_for_civi_booking=False,
            eligibility_reason="catalog_repository_unavailable",
            booking_mode="unavailable",
            operational_status="unknown",
            error="catalog_repository_unavailable",
        )
    data = repo.booking_eligibility(site_id)
    return BookingEligibilityResponse(**data)
