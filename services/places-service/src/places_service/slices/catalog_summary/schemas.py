from __future__ import annotations

from pydantic import BaseModel, Field


class CatalogSummaryResponse(BaseModel):
    success: bool = True
    source_records: int = 0
    unique_entities: int = 0
    unique_sites: int = 0
    by_actor_type: dict[str, int] = Field(default_factory=dict)
    by_operational_status: dict[str, int] = Field(default_factory=dict)
    partners: int = 0
    bookable: int = 0
    geocoded: int = 0
    pending_geocoding: int = 0
    manual_review: int = 0
    duplicate_candidates: int = 0
    invalid_addresses: int = 0
    invalid_phones: int | None = None
    invalid_documents: int | None = None
    absent_from_snapshot: int | None = None
    pending_geocoding_detail: dict | None = None
    latest_import: dict | None = None
    source_updated_at: str | None = None
    snapshot_at: str | None = None
    error: str | None = None

    model_config = {"extra": "ignore"}
