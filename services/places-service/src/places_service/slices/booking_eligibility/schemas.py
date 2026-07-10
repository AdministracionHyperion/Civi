from __future__ import annotations

from pydantic import BaseModel


class BookingEligibilityResponse(BaseModel):
    site_id: str
    exists: bool
    is_partner: bool
    is_bookable: bool
    eligible_for_civi_booking: bool
    eligibility_reason: str
    booking_mode: str
    operational_status: str
    snapshot_presence: str | None = None
    source_presence_status: str | None = None
    present_in_latest_snapshot: bool | None = None
    canonical_name: str | None = None
    canonical_address: str | None = None
    canonical_city: str | None = None
    error: str | None = None
