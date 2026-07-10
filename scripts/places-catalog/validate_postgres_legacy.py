"""Validate PostgreSQL legacy places migration + national catalog import.

Creates a legacy `places` table with NOT NULL lat/lng, migrates to v1–v4,
imports the national catalog, and asserts second-apply idempotency.
"""

from __future__ import annotations

import json
import os
import sys
from pathlib import Path

from sqlalchemy import create_engine, text

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


def main() -> int:
    database_url = os.environ.get(
        "PLACES_DATABASE_URL",
        "postgresql+psycopg://civi:civi@localhost:5432/civi",
    )
    report: dict = {
        "database_url": database_url.split("@")[-1],
        "steps": [],
        "passed": False,
        "expected": EXPECTED,
    }
    try:
        # Ensure PYTHONPATH can resolve places_service
        sys.path.insert(0, str(ROOT / "services" / "places-service" / "src"))
        sys.path.insert(0, str(ROOT / "packages" / "python-common" / "src"))

        from places_service.adapters.outbound.migrate import (
            migrate_legacy_places_rows,
            migrate_schema,
        )
        from places_service.adapters.outbound.schema import places_schema_migrations
        from places_service.cli import import_catalog
        from sqlalchemy import select

        engine = create_engine(database_url, future=True)

        # a) Create legacy places with lat/lng NOT NULL
        _create_legacy_places(engine)
        report["steps"].append({"create_legacy_places": "ok"})

        # b) Confirm NOT NULL via information_schema
        lat_nullable = _column_nullable(engine, "places", "lat")
        lng_nullable = _column_nullable(engine, "places", "lng")
        if lat_nullable is not False or lng_nullable is not False:
            raise RuntimeError(f"expected NOT NULL lat/lng, got nullable lat={lat_nullable} lng={lng_nullable}")
        report["steps"].append({"legacy_not_null_confirmed": True})

        # c) Fixtures already inserted (partner + non-partner)
        with engine.connect() as conn:
            n = conn.execute(text("SELECT COUNT(*) FROM places")).scalar_one()
        if int(n) != 2:
            raise RuntimeError(f"expected 2 legacy fixtures, got {n}")
        report["steps"].append({"fixtures_inserted": 2})

        # d) migrate_schema + migrate_legacy_places_rows
        migration = migrate_schema(engine)
        legacy_migrated = migrate_legacy_places_rows(engine)
        report["steps"].append(
            {
                "migrate_schema": migration,
                "legacy_migrated": legacy_migrated,
            }
        )
        if legacy_migrated != 2:
            raise RuntimeError(f"expected legacy_migrated=2, got {legacy_migrated}")

        # e) Confirm lat/lng nullable, IDs preserved, entities non-orphan, v1/v2/v3 applied
        if _column_nullable(engine, "places", "lat") is not True:
            raise RuntimeError("places.lat still NOT NULL after migrate_schema")
        if _column_nullable(engine, "places", "lng") is not True:
            raise RuntimeError("places.lng still NOT NULL after migrate_schema")

        with engine.begin() as conn:
            versions = {
                str(row[0])
                for row in conn.execute(select(places_schema_migrations.c.version)).all()
            }
            for required in (
                "v1_baseline",
                "v2_national_catalog",
                "v3_places_production_hardening",
            ):
                if required not in versions:
                    raise RuntimeError(f"missing migration {required}: {sorted(versions)}")
            # v4 may also be present after hardening
            site_ids = {
                str(r[0])
                for r in conn.execute(text("SELECT site_id FROM places_sites")).all()
            }
            if site_ids != {"legacy-partner-01", "legacy-public-01"}:
                raise RuntimeError(f"legacy IDs not preserved: {site_ids}")
            orphans = conn.execute(
                text(
                    """
                    SELECT COUNT(*) FROM places_sites s
                    LEFT JOIN places_entities e ON e.entity_id = s.entity_id
                    WHERE e.entity_id IS NULL
                    """
                )
            ).scalar_one()
            if int(orphans) != 0:
                raise RuntimeError(f"orphan entities: {orphans}")
        report["steps"].append(
            {
                "lat_lng_nullable": True,
                "ids_preserved": True,
                "entities_non_orphan": True,
                "migrations_applied": sorted(versions),
            }
        )

        # Clear legacy-migrated sites so national import owns the catalog cleanly,
        # while keeping the migrated schema (nullable lat/lng + migration ledger).
        with engine.begin() as conn:
            conn.execute(text("DELETE FROM places_sites"))
            conn.execute(text("DELETE FROM places_entities"))
            conn.execute(text("DELETE FROM places"))
        report["steps"].append({"cleared_legacy_rows_for_national_import": True})

        # f) Full national import_catalog --apply
        report_dir = ROOT / "services" / "places-service" / "data" / "reports"
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
        recon = json.loads((report_dir / "reconciliation.json").read_text(encoding="utf-8"))
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
        report["steps"].append({"first_national_import": "ok", "by_processing_status": by_status})

        # g) Second apply idempotency
        import io
        from contextlib import redirect_stdout

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

        # h) Second migrate_schema: no new migrations
        second_migration = migrate_schema(engine)
        if second_migration.get("migrations"):
            raise RuntimeError(f"unexpected new migrations: {second_migration.get('migrations')}")
        report["steps"].append({"second_migrate_schema_empty": True})

        report["passed"] = True
    except Exception as exc:  # noqa: BLE001
        report["passed"] = False
        report["error"] = str(exc)

    REPORT.parent.mkdir(parents=True, exist_ok=True)
    REPORT.write_text(json.dumps(report, ensure_ascii=False, indent=2), encoding="utf-8")
    print(json.dumps({"passed": report.get("passed"), "path": str(REPORT)}, indent=2))
    return 0 if report.get("passed") else 1


if __name__ == "__main__":
    raise SystemExit(main())
