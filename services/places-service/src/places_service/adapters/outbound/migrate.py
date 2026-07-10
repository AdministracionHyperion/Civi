from __future__ import annotations

"""Lightweight schema migration helpers for places-service.

Does not replace a full Alembic history, but upgrades existing installs beyond
create_all() by adding nullable columns required by the national catalog model
and relaxing legacy NOT NULL constraints that block national imports.
"""

from datetime import datetime, timezone
import hashlib

from sqlalchemy import inspect, select, text
from sqlalchemy.engine import Engine

from places_service.adapters.outbound.schema import (
    create_all_tables,
    metadata,
    places_schema_migrations,
)


# Columns that may be missing on older installs (legacy `places` + new sites).
_PLACES_SITES_EXTRA = (
    ("snapshot_presence", "VARCHAR(32) DEFAULT 'present'"),
    ("last_seen_import_run_id", "VARCHAR(64)"),
    ("status_inferred_from_name", "BOOLEAN DEFAULT 0"),
    ("is_official_actor", "BOOLEAN DEFAULT 1"),
    ("is_bookable", "BOOLEAN DEFAULT 0"),
    ("booking_mode", "VARCHAR(32) DEFAULT 'information_only'"),
    ("quality_score", "FLOAT DEFAULT 0"),
    ("requires_manual_review", "BOOLEAN DEFAULT 0"),
    ("municipality_code", "VARCHAR(16)"),
    ("department_code", "VARCHAR(8)"),
    ("population_center", "VARCHAR(128)"),
    ("locality", "VARCHAR(128)"),
    ("raw_city", "VARCHAR(256)"),
    ("raw_department", "VARCHAR(256)"),
    ("geocode_status", "VARCHAR(32) DEFAULT 'not_attempted'"),
    ("geocode_provider", "VARCHAR(64)"),
    ("geocode_confidence", "FLOAT"),
    ("location_precision", "VARCHAR(32) DEFAULT 'unknown'"),
    ("operational_status", "VARCHAR(32) DEFAULT 'unknown'"),
    ("status_verified", "BOOLEAN DEFAULT 0"),
    ("status_source", "VARCHAR(64)"),
    ("source_presence_status", "VARCHAR(32) DEFAULT 'present'"),
    ("present_in_latest_snapshot", "BOOLEAN DEFAULT 1"),
    ("first_seen_import_run", "VARCHAR(64)"),
    ("last_seen_import_run", "VARCHAR(64)"),
    ("missing_since_import_run", "VARCHAR(64)"),
    ("content_hash", "VARCHAR(64)"),
    ("first_seen_at", "VARCHAR(64)"),
    ("last_seen_at", "VARCHAR(64)"),
)

_PLACES_ENTITIES_EXTRA = (
    ("content_hash", "VARCHAR(64)"),
    ("document_validation_status", "VARCHAR(32)"),
)

_PLACES_IMPORT_RUNS_EXTRA = (
    ("missing_count", "INTEGER DEFAULT 0"),
    ("reappeared_count", "INTEGER DEFAULT 0"),
    ("error_code", "VARCHAR(128)"),
    ("error_message", "TEXT"),
    ("failed_at", "VARCHAR(64)"),
)

_LEGACY_PLACES_EXTRA = (
    ("is_bookable", "BOOLEAN DEFAULT 0"),
    ("booking_mode", "VARCHAR(32) DEFAULT 'information_only'"),
    ("municipality_code", "VARCHAR(16)"),
    ("status_verified", "BOOLEAN DEFAULT 0"),
    ("location_precision", "VARCHAR(32)"),
    ("phone", "VARCHAR(64)"),
    ("status", "VARCHAR(32) DEFAULT 'unknown'"),
    ("source", "VARCHAR(32) DEFAULT 'catalog'"),
    ("source_updated_at", "VARCHAR(64)"),
    ("geocode_confidence", "FLOAT"),
    ("geocode_provider", "VARCHAR(32)"),
    ("geocode_status", "VARCHAR(32) DEFAULT 'skipped'"),
    ("runt_actor_id", "VARCHAR(128)"),
    ("nit", "VARCHAR(64)"),
)

_GEOCODE_ATTEMPTS_EXTRA = (
    ("attempt_number", "INTEGER"),
    ("provider_record_id", "VARCHAR(128)"),
    ("http_status", "INTEGER"),
    ("error_code", "VARCHAR(128)"),
    ("error_message", "TEXT"),
    ("completed_at", "VARCHAR(64)"),
)

_PRESENCE_EVENTS_EXTRA = (
    ("source", "VARCHAR(64)"),
    ("actor", "VARCHAR(128)"),
    ("reason", "VARCHAR(512)"),
)

_MIGRATION_DEFINITIONS = (
    ("v1_baseline", "create_all baseline schema"),
    ("v2_national_catalog", "national catalog history and presence columns"),
    ("v3_places_production_hardening", "nullable legacy lat/lng, presence events, document validation status"),
    ("v4_geocode_attempts_and_presence_source", "geocode attempt detail columns and presence event source"),
)


def migrate_schema(engine: Engine) -> dict[str, list[str]]:
    """Apply baseline, national-catalog, and production-hardening migrations."""
    create_all_tables(engine)
    added: dict[str, list[str]] = {
        "places_sites": [],
        "places_entities": [],
        "places_import_runs": [],
        "places": [],
        "places_geocode_attempts": [],
        "places_presence_events": [],
        "migrations": [],
        "legacy_nullability": [],
    }
    inspector = inspect(engine)
    tables = set(inspector.get_table_names())

    def add_missing_columns(table: str, columns: tuple[tuple[str, str], ...]) -> None:
        if table not in tables:
            return
        existing = {c["name"] for c in inspector.get_columns(table)}
        for name, ddl in columns:
            if name in existing:
                continue
            with engine.begin() as conn:
                conn.execute(text(f"ALTER TABLE {table} ADD COLUMN {name} {ddl}"))
            added[table].append(name)

    add_missing_columns("places_sites", _PLACES_SITES_EXTRA)
    add_missing_columns("places_entities", _PLACES_ENTITIES_EXTRA)
    add_missing_columns("places_import_runs", _PLACES_IMPORT_RUNS_EXTRA)
    add_missing_columns("places", _LEGACY_PLACES_EXTRA)
    add_missing_columns("places_geocode_attempts", _GEOCODE_ATTEMPTS_EXTRA)
    add_missing_columns("places_presence_events", _PRESENCE_EVENTS_EXTRA)

    nullability = _relax_legacy_places_coordinates(engine)
    added["legacy_nullability"].extend(nullability)

    with engine.begin() as conn:
        applied = {
            str(row[0])
            for row in conn.execute(select(places_schema_migrations.c.version)).all()
        }
        for version, name in _MIGRATION_DEFINITIONS:
            if version not in applied:
                checksum = hashlib.sha256(f"{version}:{name}".encode()).hexdigest()
                conn.execute(
                    places_schema_migrations.insert().values(
                        version=version,
                        name=name,
                        applied_at=datetime.now(timezone.utc).isoformat(),
                        checksum=checksum,
                    )
                )
                added["migrations"].append(version)

    return added


def _relax_legacy_places_coordinates(engine: Engine) -> list[str]:
    """Allow NULL lat/lng on legacy places (Strategy A)."""
    inspector = inspect(engine)
    if "places" not in set(inspector.get_table_names()):
        return []
    columns = {c["name"]: c for c in inspector.get_columns("places")}
    changed: list[str] = []
    dialect = engine.dialect.name

    for col_name in ("lat", "lng"):
        column = columns.get(col_name)
        if column is None or column.get("nullable", True):
            continue
        if dialect == "postgresql":
            with engine.begin() as conn:
                conn.execute(text(f"ALTER TABLE places ALTER COLUMN {col_name} DROP NOT NULL"))
            changed.append(f"{col_name}:drop_not_null")
        elif dialect == "sqlite":
            # SQLite cannot DROP NOT NULL in place; rebuild the table once.
            if "sqlite_rebuild_places_nullable_coords" in changed:
                continue
            _rebuild_sqlite_places_nullable_coords(engine)
            changed.append("sqlite_rebuild_places_nullable_coords")
            break
        else:
            with engine.begin() as conn:
                conn.execute(text(f"ALTER TABLE places ALTER COLUMN {col_name} DROP NOT NULL"))
            changed.append(f"{col_name}:drop_not_null")
    return changed


def _rebuild_sqlite_places_nullable_coords(engine: Engine) -> None:
    """Recreate SQLite legacy places with nullable lat/lng while preserving rows."""
    with engine.begin() as conn:
        conn.execute(text("PRAGMA foreign_keys=OFF"))
        conn.execute(
            text(
                """
                CREATE TABLE places_nullable_coords (
                    id VARCHAR(128) PRIMARY KEY,
                    name VARCHAR(255) NOT NULL,
                    address VARCHAR(512) NOT NULL,
                    city VARCHAR(128) NOT NULL,
                    department VARCHAR(128) NOT NULL,
                    kind VARCHAR(32) NOT NULL,
                    lat FLOAT,
                    lng FLOAT,
                    is_partner BOOLEAN NOT NULL,
                    phone VARCHAR(64),
                    status VARCHAR(32),
                    source VARCHAR(32),
                    source_updated_at VARCHAR(64),
                    geocode_confidence FLOAT,
                    geocode_provider VARCHAR(32),
                    geocode_status VARCHAR(32),
                    runt_actor_id VARCHAR(128),
                    nit VARCHAR(64),
                    is_bookable BOOLEAN,
                    booking_mode VARCHAR(32),
                    municipality_code VARCHAR(16),
                    status_verified BOOLEAN,
                    location_precision VARCHAR(32)
                )
                """
            )
        )
        existing = {c["name"] for c in inspect(engine).get_columns("places")}
        select_cols = [
            "id",
            "name",
            "address",
            "city",
            "department",
            "kind",
            "lat",
            "lng",
            "is_partner",
        ]
        optional = [
            "phone",
            "status",
            "source",
            "source_updated_at",
            "geocode_confidence",
            "geocode_provider",
            "geocode_status",
            "runt_actor_id",
            "nit",
            "is_bookable",
            "booking_mode",
            "municipality_code",
            "status_verified",
            "location_precision",
        ]
        for col in optional:
            if col in existing:
                select_cols.append(col)
            else:
                select_cols.append(f"NULL AS {col}")
        conn.execute(
            text(
                f"INSERT INTO places_nullable_coords ({', '.join(c.split(' AS ')[-1] for c in select_cols)}) "
                f"SELECT {', '.join(select_cols)} FROM places"
            )
        )
        conn.execute(text("DROP TABLE places"))
        conn.execute(text("ALTER TABLE places_nullable_coords RENAME TO places"))
        conn.execute(text("PRAGMA foreign_keys=ON"))


def migrate_legacy_places_rows(engine: Engine) -> int:
    """Copy legacy `places` rows into `places_sites` when sites table is empty."""
    inspector = inspect(engine)
    tables = set(inspector.get_table_names())
    if "places" not in tables or "places_sites" not in tables:
        return 0
    with engine.begin() as conn:
        sites_count = conn.execute(text("SELECT COUNT(*) FROM places_sites")).scalar_one()
        if int(sites_count or 0) > 0:
            return 0
        rows = conn.execute(text("SELECT * FROM places")).mappings().all()
        migrated = 0
        for row in rows:
            site_id = str(row["id"])
            entity_id = f"ent-legacy-{site_id}"
            if "places_entities" in tables:
                conn.execute(
                    text(
                        """
                        INSERT INTO places_entities (
                            entity_id, document_type, document_number, verification_digit,
                            document_raw, document_valid, document_validation_status,
                            legal_name, legal_name_normalized,
                            entity_status, requires_manual_review
                        ) VALUES (
                            :entity_id, 'UNKNOWN', NULL, NULL,
                            NULL, NULL, 'missing', :legal_name, :legal_name_normalized,
                            'unknown', 1
                        )
                        ON CONFLICT(entity_id) DO NOTHING
                        """
                        if engine.dialect.name == "sqlite"
                        else """
                        INSERT INTO places_entities (
                            entity_id, document_type, document_number, verification_digit,
                            document_raw, document_valid, document_validation_status,
                            legal_name, legal_name_normalized,
                            entity_status, requires_manual_review
                        ) VALUES (
                            :entity_id, 'UNKNOWN', NULL, NULL,
                            NULL, NULL, 'missing', :legal_name, :legal_name_normalized,
                            'unknown', true
                        )
                        ON CONFLICT (entity_id) DO NOTHING
                        """
                    ),
                    {
                        "entity_id": entity_id,
                        "legal_name": str(row["name"]),
                        "legal_name_normalized": str(row["name"]).upper(),
                    },
                )
            conn.execute(
                text(
                    """
                    INSERT INTO places_sites (
                        site_id, entity_id, actor_type, name, name_normalized,
                        address_raw, address_normalized, address_quality,
                        department, municipality, raw_city, raw_department,
                        lat, lng, geocode_status, location_precision,
                        operational_status, status_verified, status_inferred_from_name,
                        is_official_actor, is_partner, is_bookable, booking_mode,
                        quality_score, requires_manual_review, snapshot_presence,
                        source_presence_status, present_in_latest_snapshot
                    ) VALUES (
                        :site_id, :entity_id, :actor_type, :name, :name_normalized,
                        :address_raw, :address_normalized, :address_quality,
                        :department, :municipality, :raw_city, :raw_department,
                        :lat, :lng, :geocode_status, :location_precision,
                        :operational_status, :status_verified, :status_inferred_from_name,
                        :is_official_actor, :is_partner, :is_bookable, :booking_mode,
                        :quality_score, :requires_manual_review, :snapshot_presence,
                        :source_presence_status, :present_in_latest_snapshot
                    )
                    """
                ),
                {
                    "site_id": site_id,
                    "entity_id": entity_id,
                    "actor_type": str(row["kind"]),
                    "name": str(row["name"]),
                    "name_normalized": str(row["name"]).upper(),
                    "address_raw": str(row["address"]),
                    "address_normalized": str(row["address"]).upper(),
                    "address_quality": "partial",
                    "department": str(row["department"]),
                    "municipality": str(row["city"]),
                    "raw_city": str(row["city"]),
                    "raw_department": str(row["department"]),
                    "lat": row.get("lat"),
                    "lng": row.get("lng"),
                    "geocode_status": str(row.get("geocode_status") or "not_attempted"),
                    "location_precision": str(row.get("location_precision") or "unknown"),
                    "operational_status": str(row.get("status") or "unknown"),
                    "status_verified": bool(row.get("status_verified") or False),
                    "status_inferred_from_name": False,
                    "is_official_actor": False,
                    "is_partner": bool(row.get("is_partner") or False),
                    "is_bookable": bool(row.get("is_bookable") or False),
                    "booking_mode": str(row.get("booking_mode") or "information_only"),
                    "quality_score": 0.3,
                    "requires_manual_review": True,
                    "snapshot_presence": "present",
                    "source_presence_status": "present",
                    "present_in_latest_snapshot": True,
                },
            )
            migrated += 1
        return migrated


__all__ = ["migrate_schema", "migrate_legacy_places_rows", "metadata"]
