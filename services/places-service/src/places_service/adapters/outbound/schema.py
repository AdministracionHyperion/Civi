from __future__ import annotations

from sqlalchemy import (
    Boolean,
    Column,
    Float,
    Integer,
    MetaData,
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
    Column("document_valid", Boolean, nullable=False),
    Column("legal_name", String(512), nullable=False),
    Column("legal_name_normalized", String(512), nullable=False),
    Column("entity_status", String(32), nullable=False),
    Column("requires_manual_review", Boolean, nullable=False, default=False),
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
    Column("location_precision", String(32), nullable=False),
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
