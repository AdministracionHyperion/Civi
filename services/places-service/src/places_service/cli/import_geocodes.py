from __future__ import annotations

import argparse
import csv
import json
import os
from datetime import datetime, timezone
from pathlib import Path
from uuid import uuid4

from sqlalchemy import select

from places_service.adapters.outbound.catalog_repository import CatalogSqlRepository
from places_service.adapters.outbound.migrate import migrate_schema
from places_service.adapters.outbound.schema import places_geocode_attempts, places_sites


def _utc_now() -> str:
    return datetime.now(timezone.utc).isoformat()


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Import manually reviewed geocodes from CSV")
    parser.add_argument("--input", type=Path, required=True)
    parser.add_argument("--dry-run", action="store_true")
    parser.add_argument("--apply", action="store_true")
    parser.add_argument("--database-url", default=None)
    args = parser.parse_args(argv)
    if args.dry_run == args.apply:
        parser.error("Specify exactly one of --dry-run or --apply")

    with args.input.open(encoding="utf-8", newline="") as handle:
        rows = list(csv.DictReader(handle))
    required = {"site_id", "lat", "lng", "confidence", "provider", "precision"}
    if not rows or not required.issubset(rows[0]):
        parser.error(f"CSV must include columns: {', '.join(sorted(required))}")

    validated: list[dict[str, object]] = []
    for row_number, row in enumerate(rows, start=2):
        try:
            validated.append(
                {
                    "site_id": str(row["site_id"]).strip(),
                    "lat": float(str(row["lat"])),
                    "lng": float(str(row["lng"])),
                    "confidence": float(str(row["confidence"])),
                    "provider": str(row["provider"]).strip(),
                    "precision": str(row["precision"]).strip(),
                    "row_number": row_number,
                }
            )
        except (KeyError, TypeError, ValueError) as exc:
            parser.error(f"invalid geocode at CSV row {row_number}: {exc}")

    summary = {"mode": "dry_run" if args.dry_run else "apply", "rows": len(validated)}
    if args.dry_run:
        print(json.dumps(summary, ensure_ascii=False, indent=2))
        return 0

    database_url = args.database_url or os.getenv("PLACES_DATABASE_URL")
    if not database_url:
        database_url = "sqlite+pysqlite:///services/places-service/data/processed/places_catalog.sqlite"
    repo = CatalogSqlRepository(database_url, create_schema=False)
    migrate_schema(repo.engine)
    applied = missing = 0
    with repo.engine.begin() as conn:
        for row in validated:
            site_id = str(row["site_id"])
            site = conn.execute(
                select(places_sites.c.site_id).where(places_sites.c.site_id == site_id)
            ).first()
            if site is None:
                missing += 1
                continue
            attempted_at = _utc_now()
            conn.execute(
                places_sites.update()
                .where(places_sites.c.site_id == site_id)
                .values(
                    lat=row["lat"],
                    lng=row["lng"],
                    geocode_confidence=row["confidence"],
                    geocode_provider=row["provider"],
                    geocode_status="manual",
                    location_precision=row["precision"],
                    updated_at=attempted_at,
                )
            )
            conn.execute(
                places_geocode_attempts.insert().values(
                    attempt_id=str(uuid4()),
                    site_id=site_id,
                    import_run_id=None,
                    provider=row["provider"],
                    query=None,
                    status="manual",
                    lat=row["lat"],
                    lng=row["lng"],
                    confidence=row["confidence"],
                    precision=row["precision"],
                    response_payload=json.dumps({"csv_row": row["row_number"]}),
                    attempted_at=attempted_at,
                )
            )
            applied += 1
    print(json.dumps({**summary, "applied": applied, "unknown_site_ids": missing}, ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
