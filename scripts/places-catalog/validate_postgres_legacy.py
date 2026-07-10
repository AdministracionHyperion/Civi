"""Validate PostgreSQL legacy places migration + national catalog import.

Creates a legacy `places` table with NOT NULL lat/lng, migrates to v1–v4,
imports the national catalog while preserving legacy fixtures, and asserts
second-apply idempotency for national sites (0/0/4046).
"""

from __future__ import annotations

import io
import json
import os
import sys
from contextlib import redirect_stdout
from pathlib import Path

from sqlalchemy import create_engine, select, text

ROOT = Path(__file__).resolve().parents[2]
RAW = ROOT / "services" / "places-service" / "data" / "raw" / "places_colombia_original.json"
REPORT = (
    ROOT
    / "services"
    / "places-service"
    / "data"
    / "reports"
    / "postgresql_legacy_migration_report.json"
)

EXPECTED = {
    "input_rows": 4107,
    "imported": 4040,
    "merged": 61,
    "pending": 6,
    "rejected": 0,
    "unique_sites": 4046,
    "unique_entities": 3293,
    "second_unchanged": 4046,
}

LEGACY_IDS = {"legacy-partner-01", "legacy-public-01"}


def _column_nullable(engine, table: str, column: str) -> bool | None:
    with engine.connect() as conn:
        row = conn.execute(
            text(
                """
                SELECT is_nullable
                FROM information_schema.columns
                WHERE table_schema = 'public'
                  AND table_name = :table
                  AND column_name = :column
                """
            ),
            {"table": table, "column": column},
        ).first()
    if row is None:
        return None
    return str(row[0]).upper() == "YES"


def _create_legacy_places(engine) -> None:
    with engine.begin() as conn:
        conn.execute(text("DROP TABLE IF EXISTS places CASCADE"))
        conn.execute(
            text(
                """
                CREATE TABLE places (
                    id VARCHAR(128) PRIMARY KEY,
                    name VARCHAR(255) NOT NULL,
                    address VARCHAR(512) NOT NULL,
                    city VARCHAR(128) NOT NULL,
                    department VARCHAR(128) NOT NULL,
                    kind VARCHAR(32) NOT NULL,
                    lat DOUBLE PRECISION NOT NULL,
                    lng DOUBLE PRECISION NOT NULL,
                    is_partner BOOLEAN NOT NULL
                )
                """
            )
        )
        conn.execute(
            text(
                """
                INSERT INTO places (id, name, address, city, department, kind, lat, lng, is_partner)
                VALUES
                (
                    'legacy-partner-01',
                    'CDA Legacy Partner',
                    'Calle 1 # 1-1',
                    'Bucaramanga',
                    'Santander',
                    'CDA',
                    7.1193,
                    -73.1227,
                    true
                ),
                (
                    'legacy-public-01',
                    'CDA Legacy Public',
                    'Calle 2 # 2-2',
                    'Bogota',
                    'Bogota D.C.',
                    'CDA',
                    4.7110,
                    -74.0721,
                    false
                )
                """
            )
        )


def _last_json_object(text_blob: str) -> dict:
    chunks: list[str] = []
    buf: list[str] = []
    depth = 0
    for line in text_blob.splitlines():
        if "{" in line or depth:
            buf.append(line)
            depth += line.count("{") - line.count("}")
            if depth == 0 and buf:
                chunks.append("\n".join(buf))
                buf = []
    return json.loads(chunks[-1]) if chunks else {}


def _pg_version(engine) -> str:
    with engine.connect() as conn:
        return str(conn.execute(text("SHOW server_version")).scalar_one())


def main() -> int:
    database_url = os.environ.get(
        "PLACES_DATABASE_URL",
        "postgresql+psycopg://civi:civi@localhost:5432/civi",
    )
    report: dict = {
        "database_url": database_url.split("@")[-1],
        "postgres_version": None,
        "legacy_schema_created": False,
        "lat_nullable_before": None,
        "lng_nullable_before": None,
        "lat_nullable_after": None,
        "lng_nullable_after": None,
        "legacy_rows_before": 0,
        "legacy_rows_after": 0,
        "legacy_sites_migrated": 0,
        "legacy_entities_created": 0,
        "orphan_entities": None,
        "v1_applied": False,
        "v2_applied": False,
        "v3_applied": False,
        "national_source_rows": None,
        "national_unique_sites": None,
        "national_unique_entities": None,
        "first_apply": None,
        "second_apply": None,
        "second_migration_changes": None,
        "passed": False,
        "steps": [],
        "expected": EXPECTED,
    }
    try:
        sys.path.insert(0, str(ROOT / "services" / "places-service" / "src"))
        sys.path.insert(0, str(ROOT / "packages" / "python-common" / "src"))

        from places_service.adapters.outbound.migrate import (
            migrate_legacy_places_rows,
            migrate_schema,
        )
        from places_service.adapters.outbound.schema import places_schema_migrations
        from places_service.cli import import_catalog

        engine = create_engine(database_url, future=True)
        report["postgres_version"] = _pg_version(engine)

        _create_legacy_places(engine)
        report["legacy_schema_created"] = True
        report["steps"].append({"create_legacy_places": "ok"})

        lat_before = _column_nullable(engine, "places", "lat")
        lng_before = _column_nullable(engine, "places", "lng")
        report["lat_nullable_before"] = lat_before
        report["lng_nullable_before"] = lng_before
        if lat_before is not False or lng_before is not False:
            raise RuntimeError(
                f"expected NOT NULL lat/lng, got nullable lat={lat_before} lng={lng_before}"
            )
        report["steps"].append({"legacy_not_null_confirmed": True})

        with engine.connect() as conn:
            n = conn.execute(text("SELECT COUNT(*) FROM places")).scalar_one()
        report["legacy_rows_before"] = int(n)
        if int(n) != 2:
            raise RuntimeError(f"expected 2 legacy fixtures, got {n}")

        migration = migrate_schema(engine)
        legacy_migrated = migrate_legacy_places_rows(engine)
        report["legacy_sites_migrated"] = int(legacy_migrated)
        report["steps"].append(
            {"migrate_schema": migration, "legacy_migrated": legacy_migrated}
        )
        if legacy_migrated != 2:
            raise RuntimeError(f"expected legacy_migrated=2, got {legacy_migrated}")

        lat_after = _column_nullable(engine, "places", "lat")
        lng_after = _column_nullable(engine, "places", "lng")
        report["lat_nullable_after"] = lat_after
        report["lng_nullable_after"] = lng_after
        if lat_after is not True or lng_after is not True:
            raise RuntimeError(
                f"places.lat/lng still NOT NULL after migrate_schema "
                f"(lat={lat_after} lng={lng_after})"
            )

        with engine.begin() as conn:
            versions = {
                str(row[0])
                for row in conn.execute(select(places_schema_migrations.c.version)).all()
            }
            report["v1_applied"] = "v1_baseline" in versions
            report["v2_applied"] = "v2_national_catalog" in versions
            report["v3_applied"] = "v3_places_production_hardening" in versions
            for required in (
                "v1_baseline",
                "v2_national_catalog",
                "v3_places_production_hardening",
            ):
                if required not in versions:
                    raise RuntimeError(f"missing migration {required}: {sorted(versions)}")

            site_ids = {
                str(r[0])
                for r in conn.execute(text("SELECT site_id FROM places_sites")).all()
            }
            if site_ids != LEGACY_IDS:
                raise RuntimeError(f"legacy IDs not preserved: {site_ids}")

            partner_flags = {
                str(r[0]): bool(r[1])
                for r in conn.execute(
                    text("SELECT site_id, is_partner FROM places_sites")
                ).all()
            }
            if partner_flags.get("legacy-partner-01") is not True:
                raise RuntimeError(f"partner flag lost: {partner_flags}")
            if partner_flags.get("legacy-public-01") is not False:
                raise RuntimeError(f"non-partner flag lost: {partner_flags}")

            bookable_modes = list(
                conn.execute(
                    text(
                        """
                        SELECT site_id, is_bookable, booking_mode, operational_status
                        FROM places_sites
                        """
                    )
                ).mappings()
            )
            for row in bookable_modes:
                if bool(row["is_bookable"]):
                    raise RuntimeError(f"invented is_bookable on legacy: {dict(row)}")
                if str(row["booking_mode"] or "") not in {
                    "information_only",
                    "unavailable",
                    "civi",
                }:
                    raise RuntimeError(f"unexpected booking_mode: {dict(row)}")
                # Conservative: must not invent active
                if str(row["operational_status"] or "") == "active":
                    raise RuntimeError(f"invented active status: {dict(row)}")

            entity_count = int(
                conn.execute(text("SELECT COUNT(*) FROM places_entities")).scalar_one()
            )
            report["legacy_entities_created"] = entity_count
            if entity_count < 1:
                raise RuntimeError("expected legacy entities to be created")

            orphans = int(
                conn.execute(
                    text(
                        """
                        SELECT COUNT(*) FROM places_sites s
                        LEFT JOIN places_entities e ON e.entity_id = s.entity_id
                        WHERE e.entity_id IS NULL
                        """
                    )
                ).scalar_one()
            )
            report["orphan_entities"] = orphans
            if orphans != 0:
                raise RuntimeError(f"orphan entities: {orphans}")

            legacy_places_count = int(
                conn.execute(text("SELECT COUNT(*) FROM places")).scalar_one()
            )
            report["legacy_rows_after"] = legacy_places_count

        report["steps"].append(
            {
                "lat_lng_nullable": True,
                "ids_preserved": True,
                "entities_non_orphan": True,
                "migrations_applied": sorted(versions),
                "partner_flags": partner_flags,
            }
        )

        # National import coexists with legacy fixtures (do not delete them).
        report_dir = ROOT / "services" / "places-service" / "data" / "reports"
        buf_first = io.StringIO()
        with redirect_stdout(buf_first):
            first_rc = import_catalog.main(
                [
                    "--input",
                    str(RAW),
                    "--apply",
                    "--database-url",
                    database_url,
                    "--report-dir",
                    str(report_dir),
                ]
            )
        if first_rc != 0:
            raise RuntimeError(f"first import failed rc={first_rc}")
        first_counts = _last_json_object(buf_first.getvalue())
        report["first_apply"] = {
            "inserted": first_counts.get("inserted"),
            "updated": first_counts.get("updated"),
            "unchanged": first_counts.get("unchanged"),
        }

        recon = json.loads((report_dir / "reconciliation.json").read_text(encoding="utf-8"))
        report["national_source_rows"] = recon.get("input_rows")
        report["national_unique_sites"] = recon.get("unique_sites")
        report["national_unique_entities"] = recon.get("unique_entities")
        report["reconciliation"] = {
            "input_rows": recon.get("input_rows"),
            "unique_sites": recon.get("unique_sites"),
            "unique_entities": recon.get("unique_entities"),
            "by_processing_status": recon.get("by_processing_status"),
            "sum_matches_input": recon.get("sum_matches_input"),
        }
        by_status = recon.get("by_processing_status") or {}
        if recon.get("input_rows") != EXPECTED["input_rows"]:
            raise RuntimeError(f"input_rows mismatch: {recon.get('input_rows')}")
        if recon.get("unique_sites") != EXPECTED["unique_sites"]:
            raise RuntimeError(f"unique_sites mismatch: {recon.get('unique_sites')}")
        if recon.get("unique_entities") != EXPECTED["unique_entities"]:
            raise RuntimeError(f"unique_entities mismatch: {recon.get('unique_entities')}")
        imported = int(by_status.get("imported_as_site") or 0)
        merged = int(by_status.get("merged_duplicate") or 0)
        pending = int(by_status.get("pending_review") or 0)
        rejected = int(recon.get("rejected") or by_status.get("rejected") or 0)
        if (
            imported != EXPECTED["imported"]
            or merged != EXPECTED["merged"]
            or pending != EXPECTED["pending"]
            or rejected != EXPECTED["rejected"]
        ):
            raise RuntimeError(
                f"status counts mismatch: imported={imported} merged={merged} "
                f"pending={pending} rejected={rejected} raw={by_status}"
            )

        with engine.connect() as conn:
            remaining_legacy = {
                str(r[0])
                for r in conn.execute(
                    text(
                        "SELECT site_id FROM places_sites WHERE site_id IN "
                        "('legacy-partner-01','legacy-public-01')"
                    )
                ).all()
            }
            if remaining_legacy != LEGACY_IDS:
                raise RuntimeError(f"legacy fixtures lost after national import: {remaining_legacy}")
            partner_after = {
                str(r[0]): bool(r[1])
                for r in conn.execute(
                    text(
                        "SELECT site_id, is_partner FROM places_sites "
                        "WHERE site_id IN ('legacy-partner-01','legacy-public-01')"
                    )
                ).all()
            }
            if partner_after != partner_flags:
                raise RuntimeError(
                    f"commercial flags changed after national import: {partner_after}"
                )
            total_sites = int(conn.execute(text("SELECT COUNT(*) FROM places_sites")).scalar_one())
            # National unique sites + 2 legacy fixtures that coexist by design
            if total_sites < EXPECTED["unique_sites"] + 2:
                raise RuntimeError(
                    f"expected at least {EXPECTED['unique_sites'] + 2} sites "
                    f"(national + legacy), got {total_sites}"
                )
            null_coord_errors = int(
                conn.execute(
                    text(
                        """
                        SELECT COUNT(*) FROM places_sites
                        WHERE (lat IS NULL AND lng IS NOT NULL)
                           OR (lat IS NOT NULL AND lng IS NULL)
                        """
                    )
                ).scalar_one()
            )
            if null_coord_errors:
                raise RuntimeError(f"half-null coordinates: {null_coord_errors}")

        report["steps"].append(
            {
                "first_national_import": "ok",
                "by_processing_status": by_status,
                "legacy_preserved": True,
                "total_sites": total_sites,
            }
        )

        buf = io.StringIO()
        with redirect_stdout(buf):
            second_rc = import_catalog.main(
                [
                    "--input",
                    str(RAW),
                    "--apply",
                    "--database-url",
                    database_url,
                    "--report-dir",
                    str(report_dir),
                ]
            )
        if second_rc != 0:
            raise RuntimeError(f"second import failed rc={second_rc}")
        second_counts = _last_json_object(buf.getvalue())
        report["second_apply"] = {
            "inserted": second_counts.get("inserted"),
            "updated": second_counts.get("updated"),
            "unchanged": second_counts.get("unchanged"),
        }
        if (
            second_counts.get("inserted") != 0
            or second_counts.get("updated") != 0
            or int(second_counts.get("unchanged") or 0) != EXPECTED["second_unchanged"]
        ):
            raise RuntimeError(f"second apply not idempotent: {report['second_apply']}")
        report["steps"].append({"second_apply_idempotent": True})

        with engine.connect() as conn:
            remaining_legacy = {
                str(r[0])
                for r in conn.execute(
                    text(
                        "SELECT site_id FROM places_sites WHERE site_id IN "
                        "('legacy-partner-01','legacy-public-01')"
                    )
                ).all()
            }
            if remaining_legacy != LEGACY_IDS:
                raise RuntimeError(f"legacy fixtures lost after second import: {remaining_legacy}")

        second_migration = migrate_schema(engine)
        report["second_migration_changes"] = {
            "migrations": second_migration.get("migrations") or [],
            "places": second_migration.get("places") or [],
            "places_sites": second_migration.get("places_sites") or [],
            "legacy_nullability": second_migration.get("legacy_nullability") or [],
        }
        if second_migration.get("migrations"):
            raise RuntimeError(f"unexpected new migrations: {second_migration.get('migrations')}")
        if second_migration.get("legacy_nullability"):
            raise RuntimeError(
                f"unexpected nullability changes on second migrate: "
                f"{second_migration.get('legacy_nullability')}"
            )
        report["steps"].append({"second_migrate_schema_empty": True})

        report["passed"] = True
    except Exception as exc:  # noqa: BLE001
        report["passed"] = False
        report["error"] = str(exc)

    REPORT.parent.mkdir(parents=True, exist_ok=True)
    REPORT.write_text(json.dumps(report, ensure_ascii=False, indent=2), encoding="utf-8")
    print(json.dumps({"passed": report.get("passed"), "path": str(REPORT)}, indent=2))
    if not report.get("passed"):
        print(json.dumps({"error": report.get("error")}, indent=2), file=sys.stderr)
    return 0 if report.get("passed") else 1


if __name__ == "__main__":
    raise SystemExit(main())
