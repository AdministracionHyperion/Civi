from __future__ import annotations

from sqlalchemy import (
    Boolean,
    Column,
    Float,
    Integer,
    MetaData,
    PrimaryKeyConstraint,
    String,
    Table,
    Text,
    create_engine,
    select,
)
from sqlalchemy.engine import Engine

metadata = MetaData()

places_entities = Table(
    "places_entities",
    metadata,
    Column("entity_id", String(128), primary_key=True),
    Column("document_type", String(32), nullable=False),
    Column("document_number", String(64), nullable=True, index=True),
    Column("verification_digit", String(4), nullable=True),
    Column("document_raw", String(128), nullable=True),
    Column("document_valid", Boolean, nullable=True),
    Column("document_validation_status", String(32), nullable=True, index=True),
    Column("legal_name", String(512), nullable=False),
    Column("legal_name_normalized", String(512), nullable=False),
    Column("entity_status", String(32), nullable=False),
    Column("requires_manual_review", Boolean, nullable=False, default=False),
    Column("content_hash", String(64), nullable=True, index=True),
    Column("created_at", String(64), nullable=True),
    Column("updated_at", String(64), nullable=True),
)

places_sites = Table(
    "places_sites",
    metadata,
    Column("site_id", String(128), primary_key=True),
    Column("entity_id", String(128), nullable=False, index=True),
    Column("actor_type", String(8), nullable=False, index=True),
    Column("source_actor_id", String(128), nullable=True, index=True),
    # Official RUNT/source JSON `id` (NOT the hashed site_id). Enables resolving
    # authoritative geocode files (e.g. Manizales) back to catalog sites.
    Column("source_place_id", String(128), nullable=True, index=True),
    Column("name", String(512), nullable=False),
    Column("name_normalized", String(512), nullable=False),
    Column("trade_name", String(512), nullable=True),
    Column("address_raw", String(1024), nullable=False),
    Column("address_normalized", String(1024), nullable=False),
    Column("address_quality", String(32), nullable=False),
    Column("department", String(128), nullable=False),
    Column("department_code", String(8), nullable=True),
    Column("municipality", String(128), nullable=False, index=True),
    Column("municipality_code", String(16), nullable=True, index=True),
    Column("population_center", String(128), nullable=True),
    Column("locality", String(128), nullable=True),
    Column("raw_city", String(256), nullable=False),
    Column("raw_department", String(256), nullable=False),
    Column("lat", Float, nullable=True),
    Column("lng", Float, nullable=True),
    Column("geocode_status", String(32), nullable=False, index=True),
    Column("geocode_provider", String(64), nullable=True),
    Column("geocode_confidence", Float, nullable=True),
    Column("location_precision", String(64), nullable=False),
    # Geocode VALIDATION result (not operational status): confirmed_business,
    # confirmed_address, approximate_not_confirmed. Nullable until validated.
    Column("geocode_validation_status", String(64), nullable=True, index=True),
    Column("operational_status", String(32), nullable=False, index=True),
    Column("status_verified", Boolean, nullable=False),
    Column("status_source", String(64), nullable=True),
    Column("status_inferred_from_name", Boolean, nullable=False, default=False),
    Column("is_official_actor", Boolean, nullable=False, default=True),
    Column("is_partner", Boolean, nullable=False, index=True),
    Column("is_bookable", Boolean, nullable=False, index=True),
    Column("booking_mode", String(32), nullable=False),
    Column("quality_score", Float, nullable=False),
    Column("requires_manual_review", Boolean, nullable=False, index=True),
    Column("snapshot_presence", String(32), nullable=False, default="present", index=True),
    Column("last_seen_import_run_id", String(64), nullable=True, index=True),
    Column("source_presence_status", String(32), nullable=False, default="present", index=True),
    Column("present_in_latest_snapshot", Boolean, nullable=False, default=True, index=True),
    Column("first_seen_import_run", String(64), nullable=True, index=True),
    Column("last_seen_import_run", String(64), nullable=True, index=True),
    Column("missing_since_import_run", String(64), nullable=True, index=True),
    Column("content_hash", String(64), nullable=True, index=True),
    Column("first_seen_at", String(64), nullable=True),
    Column("last_seen_at", String(64), nullable=True),
    Column("created_at", String(64), nullable=True),
    Column("updated_at", String(64), nullable=True),
)

places_contacts = Table(
    "places_contacts",
    metadata,
    Column("contact_id", String(128), primary_key=True),
    Column("site_id", String(128), nullable=False, index=True),
    Column("contact_type", String(32), nullable=False),
    Column("value_raw", String(128), nullable=False),
    Column("value_normalized", String(64), nullable=True),
    Column("e164", String(32), nullable=True),
    Column("is_valid", Boolean, nullable=False),
    Column("is_public", Boolean, nullable=False),
    Column("source_record_id", String(128), nullable=True),
)

places_source_records = Table(
    "places_source_records",
    metadata,
    Column("source_record_id", String(128), primary_key=True),
    Column("import_run_id", String(64), nullable=False, index=True),
    Column("source_name", String(128), nullable=False),
    Column("source_row_number", Integer, nullable=False),
    Column("source_payload", Text, nullable=False),
    Column("source_hash", String(64), nullable=False),
    Column("matched_entity_id", String(128), nullable=True),
    Column("matched_site_id", String(128), nullable=True),
    Column("processing_status", String(64), nullable=False, index=True),
    Column("processing_flags", Text, nullable=False),
)

places_schema_migrations = Table(
    "places_schema_migrations",
    metadata,
    Column("version", String(64), primary_key=True),
    Column("name", String(256), nullable=False),
    Column("applied_at", String(64), nullable=False),
    Column("checksum", String(64), nullable=False),
)

places_import_source_records = Table(
    "places_import_source_records",
    metadata,
    Column("import_run_id", String(64), nullable=False),
    Column("source_record_id", String(128), nullable=False),
    Column("source_row_number", Integer, nullable=False),
    Column("source_hash", String(64), nullable=False),
    Column("observed_payload", Text, nullable=False),
    Column("processing_status", String(64), nullable=False, index=True),
    Column("processing_flags", Text, nullable=False),
    Column("matched_entity_id", String(128), nullable=True),
    Column("matched_site_id", String(128), nullable=True),
    Column("observed_at", String(64), nullable=False),
    PrimaryKeyConstraint("import_run_id", "source_record_id"),
)

places_geocode_attempts = Table(
    "places_geocode_attempts",
    metadata,
    Column("attempt_id", String(64), primary_key=True),
    Column("site_id", String(128), nullable=False, index=True),
    Column("import_run_id", String(64), nullable=True, index=True),
    Column("provider", String(64), nullable=False),
    Column("query", Text, nullable=True),
    Column("status", String(32), nullable=False, index=True),
    Column("attempt_number", Integer, nullable=True),
    Column("provider_record_id", String(128), nullable=True),
    Column("http_status", Integer, nullable=True),
    Column("lat", Float, nullable=True),
    Column("lng", Float, nullable=True),
    Column("confidence", Float, nullable=True),
    Column("precision", String(32), nullable=True),
    Column("response_payload", Text, nullable=True),
    Column("error_code", String(128), nullable=True),
    Column("error_message", Text, nullable=True),
    Column("attempted_at", String(64), nullable=False),
    Column("completed_at", String(64), nullable=True),
)

places_presence_events = Table(
    "places_presence_events",
    metadata,
    Column("event_id", String(64), primary_key=True),
    Column("site_id", String(128), nullable=False, index=True),
    Column("import_run_id", String(64), nullable=True, index=True),
    Column("previous_status", String(32), nullable=True),
    Column("new_status", String(32), nullable=False),
    Column("event_type", String(64), nullable=False, index=True),
    Column("reason", String(512), nullable=True),
    Column("actor", String(128), nullable=True),
    Column("source", String(64), nullable=True),
    Column("created_at", String(64), nullable=False),
)

places_import_runs = Table(
    "places_import_runs",
    metadata,
    Column("import_run_id", String(64), primary_key=True),
    Column("source_name", String(128), nullable=False),
    Column("input_filename", String(512), nullable=False),
    Column("input_sha256", String(64), nullable=False, index=True),
    Column("started_at", String(64), nullable=False),
    Column("completed_at", String(64), nullable=True),
    Column("status", String(32), nullable=False),
    Column("source_record_count", Integer, nullable=False),
    Column("inserted_count", Integer, nullable=False),
    Column("updated_count", Integer, nullable=False),
    Column("unchanged_count", Integer, nullable=False),
    Column("merged_count", Integer, nullable=False),
    Column("rejected_count", Integer, nullable=False),
    Column("review_count", Integer, nullable=False),
    Column("report_path", String(512), nullable=True),
    Column("source_updated_at", String(64), nullable=True),
    Column("snapshot_at", String(64), nullable=True),
    Column("missing_count", Integer, nullable=False, default=0),
    Column("reappeared_count", Integer, nullable=False, default=0),
    Column("error_code", String(128), nullable=True),
    Column("error_message", Text, nullable=True),
    Column("failed_at", String(64), nullable=True),
)

places_duplicate_candidates = Table(
    "places_duplicate_candidates",
    metadata,
    Column("candidate_id", String(64), primary_key=True),
    Column("import_run_id", String(64), nullable=False, index=True),
    Column("site_id_a", String(128), nullable=False),
    Column("site_id_b", String(128), nullable=False),
    Column("confidence", Float, nullable=False),
    Column("reason", String(256), nullable=False),
    Column("rule", String(128), nullable=False),
    Column("status", String(32), nullable=False),
)

# Legacy compatibility table kept for older installs / sample seed.
places = Table(
    "places",
    metadata,
    Column("id", String(128), primary_key=True),
    Column("name", String(255), nullable=False),
    Column("address", String(512), nullable=False),
    Column("city", String(128), nullable=False, index=True),
    Column("department", String(128), nullable=False),
    Column("kind", String(32), nullable=False, index=True),
    Column("lat", Float, nullable=True),
    Column("lng", Float, nullable=True),
    Column("is_partner", Boolean, nullable=False, index=True),
    Column("phone", String(64), nullable=True),
    Column("status", String(32), nullable=False, index=True),
    Column("source", String(32), nullable=False),
    Column("source_updated_at", String(64), nullable=True),
    Column("geocode_confidence", Float, nullable=True),
    Column("geocode_provider", String(32), nullable=True),
    Column("geocode_status", String(32), nullable=False),
    Column("runt_actor_id", String(128), nullable=True, index=True),
    Column("nit", String(64), nullable=True),
    Column("is_bookable", Boolean, nullable=False, default=False),
    Column("booking_mode", String(32), nullable=False, default="information_only"),
    Column("municipality_code", String(16), nullable=True),
    Column("status_verified", Boolean, nullable=False, default=False),
    Column("location_precision", String(32), nullable=True),
)


def create_engine_from_url(database_url: str) -> Engine:
    return create_engine(database_url, future=True)


def create_all_tables(engine: Engine) -> None:
    metadata.create_all(engine)
