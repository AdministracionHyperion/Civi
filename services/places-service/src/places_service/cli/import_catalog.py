from __future__ import annotations

import argparse
import json
from datetime import datetime, timezone
from pathlib import Path
from uuid import uuid4

from places_service.adapters.outbound.catalog_repository import CatalogSqlRepository
from places_service.domain.models import ImportRun
from places_service.pipeline.catalog_builder import build_catalog_from_rows, write_reports


def _utc_now() -> str:
    return datetime.now(timezone.utc).isoformat()


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Import national places catalog (idempotent)")
    parser.add_argument(
        "--input",
        type=Path,
        default=Path("services/places-service/data/raw/places_colombia_original.json"),
    )
    parser.add_argument("--dry-run", action="store_true")
    parser.add_argument("--apply", action="store_true")
    parser.add_argument("--report-dir", type=Path, default=Path("services/places-service/data/reports"))
    parser.add_argument("--source-updated-at", default=None)
    parser.add_argument("--skip-geocoding", action="store_true", default=True)
    parser.add_argument("--database-url", default=None)
    args = parser.parse_args(argv)

    if not args.dry_run and not args.apply:
        parser.error("Specify --dry-run or --apply")

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

    import_run = ImportRun(
        import_run_id=import_run_id,
        source_name="places_colombia_sin_coords",
        input_filename=str(input_path),
        input_sha256=sha,
        started_at=started,
        status="dry_run" if args.dry_run else "applied",
        completed_at=_utc_now(),
        source_record_count=len(rows),
        inserted_count=recon["unique_sites"],
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

    summary = {
        "mode": "dry_run" if args.dry_run else "apply",
        "input": str(input_path),
        "sha256": sha,
        "reconciliation": recon,
        "unique_sites": recon["unique_sites"],
        "unique_entities": recon["unique_entities"],
        "report_dir": str(args.report_dir),
        "skip_geocoding": args.skip_geocoding,
    }
    print(json.dumps(summary, ensure_ascii=False, indent=2))

    if args.apply:
        database_url = args.database_url or __import__("os").getenv("PLACES_DATABASE_URL")
        if not database_url:
            # default local sqlite for apply in tests/dev
            database_url = "sqlite+pysqlite:///services/places-service/data/processed/places_catalog.sqlite"
        repo = CatalogSqlRepository(database_url, create_schema=True)
        counts = repo.apply_import(
            import_run=import_run,
            entities=catalog["entities"],
            sites=catalog["sites"],
            contacts=catalog["contacts"],
            source_records=catalog["source_records"],
            duplicate_candidates=catalog["duplicate_candidates"],
        )
        print(json.dumps({"applied": True, "database_url": database_url, **counts}, ensure_ascii=False, indent=2))

    return 0


if __name__ == "__main__":
    raise SystemExit(main())
