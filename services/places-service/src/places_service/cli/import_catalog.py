from __future__ import annotations

import argparse
import json
import os
import re
from datetime import datetime, timezone
from pathlib import Path
from uuid import uuid4

from places_service.adapters.outbound.catalog_repository import CatalogSqlRepository
from places_service.adapters.outbound.geocoding.provider import geocoder_from_env
from places_service.adapters.outbound.migrate import migrate_legacy_places_rows, migrate_schema
from places_service.domain.models import ImportRun
from places_service.pipeline.catalog_builder import build_catalog_from_rows, write_reports


def _utc_now() -> str:
    return datetime.now(timezone.utc).isoformat()


def _sanitize_database_url(url: str) -> str:
    return re.sub(r":([^:@/]+)@", ":***@", url)


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Import national places catalog (idempotent)")
    parser.add_argument(
        "--input",
        type=Path,
        default=Path("services/places-service/data/raw/places_colombia_original.json"),
    )
    mode = parser.add_mutually_exclusive_group(required=True)
    mode.add_argument("--dry-run", action="store_true")
    mode.add_argument("--apply", action="store_true")
    parser.add_argument("--report-dir", type=Path, default=Path("services/places-service/data/reports"))
    parser.add_argument("--source-updated-at", default=None)
    geocode = parser.add_mutually_exclusive_group()
    geocode.add_argument(
        "--skip-geocoding",
        action="store_true",
        default=None,
        help="Skip geocoding (default when neither geocoding flag is set).",
    )
    geocode.add_argument(
        "--no-skip-geocoding",
        action="store_true",
        help="Deprecated alias for --with-geocoding.",
    )
    geocode.add_argument(
        "--with-geocoding",
        action="store_true",
        help="Use PLACES_GEOCODING_MODE provider during import.",
    )
    parser.add_argument("--database-url", default=None)
    parser.add_argument(
        "--migrate-legacy",
        action="store_true",
        help="Copy legacy places rows into places_sites if empty",
    )
    args = parser.parse_args(argv)

    skip_geocoding = True
    if args.with_geocoding or args.no_skip_geocoding:
        skip_geocoding = False
    elif args.skip_geocoding:
        skip_geocoding = True

    input_path = args.input.resolve()
    if not input_path.exists():
        raise SystemExit(f"input not found: {input_path}")

    rows = json.loads(input_path.read_text(encoding="utf-8"))
    if not isinstance(rows, list):
        raise SystemExit("input JSON must be a list of records")

    import_run_id = str(uuid4())
    started = _utc_now()
    import hashlib

    data = input_path.read_bytes()
    sha = hashlib.sha256(data).hexdigest()

    catalog = build_catalog_from_rows(rows, import_run_id=import_run_id)
    recon = catalog["reconciliation"]
    if not recon["sum_matches_input"]:
        raise SystemExit(f"reconciliation mismatch: {recon}")
    if not recon.get("non_merged_equals_unique_sites", True):
        raise SystemExit(f"site count mismatch vs non-merged rows: {recon}")

    import_run = ImportRun(
        import_run_id=import_run_id,
        source_name="places_colombia_sin_coords",
        input_filename=str(input_path),
        input_sha256=sha,
        started_at=started,
        status="dry_run" if args.dry_run else "applied",
        completed_at=_utc_now(),
        source_record_count=len(rows),
        inserted_count=0,
        updated_count=0,
        unchanged_count=0,
        merged_count=recon["merged_duplicates"],
        rejected_count=recon["rejected"],
        review_count=sum(1 for s in catalog["sites"] if s.requires_manual_review),
        report_path=str(args.report_dir),
        source_updated_at=args.source_updated_at,
        snapshot_at=started,
    )

    write_reports(catalog, args.report_dir, import_run=import_run)

    geocode_stats = None
    if not skip_geocoding:
        geocoder = geocoder_from_env()
        geocode_stats = {"attempted": 0, "success": 0, "failed": 0, "skipped": 0}
        for site in catalog["sites"]:
            if site.lat is not None and site.lng is not None:
                geocode_stats["skipped"] += 1
                continue
            if site.geocode_status == "insufficient_address":
                geocode_stats["skipped"] += 1
                continue
            query = f"{site.address_raw}, {site.municipality}, {site.department}, Colombia"
            result = geocoder.geocode(query, site_id=site.site_id)
            geocode_stats["attempted"] += 1
            site.geocode_provider = result.provider
            site.geocode_status = result.status
            site.geocode_confidence = result.confidence
            if result.status == "success" and result.lat is not None and result.lng is not None:
                site.lat = result.lat
                site.lng = result.lng
                site.location_precision = result.precision
                geocode_stats["success"] += 1
            else:
                geocode_stats["failed"] += 1

    summary = {
        "mode": "dry_run" if args.dry_run else "apply",
        "input": str(input_path),
        "sha256": sha,
        "reconciliation": recon,
        "unique_sites": recon["unique_sites"],
        "unique_entities": recon["unique_entities"],
        "report_dir": str(args.report_dir),
        "skip_geocoding": skip_geocoding,
        "geocode_stats": geocode_stats,
        "site_id_collisions": len(catalog.get("site_id_collisions") or []),
    }
    print(json.dumps(summary, ensure_ascii=False, indent=2))

    if args.apply:
        database_url = args.database_url or os.getenv("PLACES_DATABASE_URL")
        if not database_url:
            raise SystemExit(
                "apply requires --database-url or PLACES_DATABASE_URL; "
                "refusing to use an implicit SQLite default"
            )
        repo = CatalogSqlRepository(database_url, create_schema=False)
        migration = migrate_schema(repo.engine)
        legacy = migrate_legacy_places_rows(repo.engine) if args.migrate_legacy else 0
        counts = repo.apply_import(
            import_run=import_run,
            entities=catalog["entities"],
            sites=catalog["sites"],
            contacts=catalog["contacts"],
            source_records=catalog["source_records"],
            duplicate_candidates=catalog["duplicate_candidates"],
        )
        print(
            json.dumps(
                {
                    "applied": True,
                    "database_url": _sanitize_database_url(database_url),
                    "migration": migration,
                    "legacy_migrated": legacy,
                    **counts,
                },
                ensure_ascii=False,
                indent=2,
            )
        )

    return 0


if __name__ == "__main__":
    raise SystemExit(main())
