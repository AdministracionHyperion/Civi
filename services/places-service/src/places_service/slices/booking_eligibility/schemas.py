from __future__ import annotations

from pydantic import BaseModel


class BookingEligibilityResponse(BaseModel):
    site_id: str
    exists: bool
    is_partner: bool
    is_bookable: bool
    booking_mode: str
    operational_status: str
    canonical_name: str | None = None
    canonical_address: str | None = None
    canonical_city: str | None = None
    error: str | None = None
