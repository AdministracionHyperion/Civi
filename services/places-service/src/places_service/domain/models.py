from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any


ACTOR_TYPES = frozenset({"CDA", "CEA", "CIA", "CRC"})

OPERATIONAL_STATUSES = frozenset(
    {"active", "inactive", "suspended", "retired", "unknown"}
)
BOOKING_MODES = frozenset({"civi", "external_contact", "information_only", "unavailable"})
GEOCODE_STATUSES = frozenset(
    {
        "not_attempted",
        "insufficient_address",
        "pending",
        "success",
        "failed",
        "manual",
        "low_confidence",
    }
)
LOCATION_PRECISIONS = frozenset(
    {
        # Generic precisions used across the catalog.
        "rooftop",
        "address",
        "street",
        "neighborhood",
        "municipality",
        "manual",
        "unknown",
        # Precisions emitted by validated city geocode files (Manizales / Santander).
        "street_intersection",
        "building",
        "business",
        "street_interpolation",
        "address_neighbour",
        "business_complex",
        "neighbourhood_address",
        "nearby_address_landmark",
        "address_interpolation",
        "route_landmark",
        "route_intersection",
        "same_street_anchor",
        "route_kilometre_anchor",
    }
)
# Geocode VALIDATION statuses (distinct from operational status). `approximate_*`
# must never be surfaced as a confirmed location.
GEOCODE_VALIDATION_STATUSES = frozenset(
    {"confirmed_business", "confirmed_address", "approximate_not_confirmed"}
)
CONFIRMED_VALIDATION_STATUSES = frozenset({"confirmed_business", "confirmed_address"})
ADDRESS_QUALITIES = frozenset({"valid", "partial", "missing", "invalid"})
PROCESSING_STATUSES = frozenset(
    {"imported_as_site", "merged_duplicate", "pending_review", "rejected_with_reason"}
)


@dataclass
class Entity:
    entity_id: str
    document_type: str
    document_number: str | None
    verification_digit: str | None
    document_raw: str | None
    document_valid: bool | None
    legal_name: str
    legal_name_normalized: str
    entity_status: str = "unknown"
    requires_manual_review: bool = False
    document_validation_status: str | None = None
    content_hash: str | None = None
    created_at: str | None = None
    updated_at: str | None = None


@dataclass
class Site:
    site_id: str
    entity_id: str
    actor_type: str
    name: str
    name_normalized: str
    address_raw: str
    address_normalized: str
    address_quality: str
    department: str
    municipality: str
    raw_city: str
    raw_department: str
    source_actor_id: str | None = None
    source_place_id: str | None = None
    trade_name: str | None = None
    department_code: str | None = None
    municipality_code: str | None = None
    population_center: str | None = None
    locality: str | None = None
    lat: float | None = None
    lng: float | None = None
    geocode_status: str = "not_attempted"
    geocode_provider: str | None = None
    geocode_confidence: float | None = None
    location_precision: str = "unknown"
    geocode_validation_status: str | None = None
    operational_status: str = "unknown"
    status_verified: bool = False
    status_source: str | None = None
    status_inferred_from_name: bool = False
    is_official_actor: bool = True
    is_partner: bool = False
    is_bookable: bool = False
    booking_mode: str = "information_only"
    quality_score: float = 0.0
    requires_manual_review: bool = False
    snapshot_presence: str = "present"
    last_seen_import_run_id: str | None = None
    source_presence_status: str = "present"
    present_in_latest_snapshot: bool = True
    first_seen_import_run: str | None = None
    last_seen_import_run: str | None = None
    missing_since_import_run: str | None = None
    content_hash: str | None = None
    first_seen_at: str | None = None
    last_seen_at: str | None = None
    created_at: str | None = None
    updated_at: str | None = None


@dataclass
class Contact:
    contact_id: str
    site_id: str
    contact_type: str
    value_raw: str
    value_normalized: str | None
    e164: str | None
    is_valid: bool
    is_public: bool = False
    source_record_id: str | None = None


@dataclass
class SourceRecord:
    source_record_id: str
    import_run_id: str
    source_name: str
    source_row_number: int
    source_payload: dict[str, Any]
    source_hash: str
    matched_entity_id: str | None = None
    matched_site_id: str | None = None
    processing_status: str = "pending_review"
    processing_flags: list[str] = field(default_factory=list)
    observed_at: str | None = None


@dataclass
class DuplicateCandidate:
    candidate_id: str
    import_run_id: str
    site_id_a: str
    site_id_b: str
    confidence: float
    reason: str
    rule: str
    status: str = "pending"


@dataclass
class ImportRun:
    import_run_id: str
    source_name: str
    input_filename: str
    input_sha256: str
    started_at: str
    status: str
    completed_at: str | None = None
    source_record_count: int = 0
    inserted_count: int = 0
    updated_count: int = 0
    unchanged_count: int = 0
    merged_count: int = 0
    rejected_count: int = 0
    review_count: int = 0
    report_path: str | None = None
    source_updated_at: str | None = None
    snapshot_at: str | None = None
    missing_count: int = 0
    reappeared_count: int = 0
    error_code: str | None = None
    error_message: str | None = None
    failed_at: str | None = None
