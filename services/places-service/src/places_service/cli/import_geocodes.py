from __future__ import annotations

import argparse
import csv
import json
import os
import re
from datetime import datetime, timezone
from pathlib import Path
from uuid import uuid4

from civi_common.geo import is_colombia_latlng
from sqlalchemy import select

from places_service.adapters.outbound.catalog_repository import CatalogSqlRepository
from places_service.adapters.outbound.migrate import migrate_schema
from places_service.adapters.outbound.schema import places_geocode_attempts, places_sites

ALLOWED_PRECISION = {
    "rooftop",
    "address",
    "street",
    "neighborhood",
    "municipality",
    "manual",
    "unknown",
}


def _utc_now() -> str:
    return datetime.now(timezone.utc).isoformat()


def _sanitize_database_url(url: str) -> str:
    return re.sub(r":([^:@/]+)@", ":***@", url)


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Import manually reviewed geocodes from CSV")
    parser.add_argument("--input", type=Path, required=True)
    mode = parser.add_mutually_exclusive_group(required=True)
    mode.add_argument("--dry-run", action="store_true")
    mode.add_argument("--apply", action="store_true")
    parser.add_argument("--database-url", default=None)
    parser.add_argument("--force", action="store_true", help="Overwrite lower-confidence existing coords")
    parser.add_argument(
        "--force-manual",
        action="store_true",
        help="Overwrite existing manual geocode_status coordinates",
    )
    parser.add_argument(
        "--report-path",
        type=Path,
        default=Path("services/places-service/data/reports/geocode_import_report.json"),
    )
    args = parser.parse_args(argv)

    with args.input.open(encoding="utf-8", newline="") as handle:
        rows = list(csv.DictReader(handle))
    required = {"site_id", "lat", "lng", "confidence", "provider", "precision"}
    if not rows or not required.issubset(set(rows[0].keys())):
        parser.error(f"CSV must include columns: {', '.join(sorted(required))}")

    counts = {
        "mode": "dry_run" if args.dry_run else "apply",
        "rows": 0,
        "inserted": 0,
        "updated": 0,
        "unchanged": 0,
        "skipped": 0,
        "rejected": 0,
        "unknown_site_ids": 0,
        "outside_colombia": 0,
        "lower_confidence_skipped": 0,
        "manual_protected": 0,
        "duplicate_site_ids": 0,
        "rejected_rows": [],
        "unknown_ids": [],
    }

    validated: list[dict[str, object]] = []
    seen_ids: set[str] = set()
    for row_number, row in enumerate(rows, start=2):
        counts["rows"] += 1
        site_id = str(row.get("site_id") or "").strip()
        provider = str(row.get("provider") or "").strip()
        precision = str(row.get("precision") or "").strip().lower()
        try:
            if not site_id:
                raise ValueError("site_id empty")
            if site_id in seen_ids:
                counts["duplicate_site_ids"] += 1
                counts["rejected"] += 1
                counts["rejected_rows"].append({"row": row_number, "reason": "duplicate_site_id"})
                continue
            seen_ids.add(site_id)
            lat = float(str(row["lat"]))
            lng = float(str(row["lng"]))
            confidence = float(str(row["confidence"]))
            if not provider:
                raise ValueError("provider empty")
            if precision not in ALLOWED_PRECISION:
                raise ValueError(f"precision invalid: {precision}")
            if not 0.0 <= confidence <= 1.0:
                raise ValueError("confidence out of range")
            if not is_colombia_latlng(lat, lng):
                counts["outside_colombia"] += 1
                counts["rejected"] += 1
                counts["rejected_rows"].append({"row": row_number, "reason": "outside_colombia"})
                continue
            validated.append(
                {
                    "site_id": site_id,
                    "lat": lat,
                    "lng": lng,
                    "confidence": confidence,
                    "provider": provider,
                    "precision": precision,
                    "row_number": row_number,
                }
            )
        except (KeyError, TypeError, ValueError) as exc:
            counts["rejected"] += 1
            counts["rejected_rows"].append({"row": row_number, "reason": str(exc)})

    database_url = args.database_url or os.getenv("PLACES_DATABASE_URL")
    if args.apply and not database_url:
        raise SystemExit(
            "apply requires --database-url or PLACES_DATABASE_URL; "
            "refusing to use an implicit SQLite default"
        )

    repo = None
    if database_url:
        repo = CatalogSqlRepository(database_url, create_schema=False)
        if args.apply:
            migrate_schema(repo.engine)

    if args.dry_run and repo is None:
        args.report_path.parent.mkdir(parents=True, exist_ok=True)
        args.report_path.write_text(json.dumps(counts, ensure_ascii=False, indent=2), encoding="utf-8")
        print(json.dumps(counts, ensure_ascii=False, indent=2))
        return 0

    assert repo is not None
    with repo.engine.begin() as conn:
        for row in validated:
            site_id = str(row["site_id"])
            site = conn.execute(select(places_sites).where(places_sites.c.site_id == site_id)).mappings().first()
            if site is None:
                counts["unknown_site_ids"] += 1
                counts["unknown_ids"].append(site_id)
                continue

            same = (
                site.get("lat") == row["lat"]
                and site.get("lng") == row["lng"]
                and float(site.get("geocode_confidence") or -1) == float(row["confidence"])
                and str(site.get("geocode_provider") or "") == row["provider"]
                and str(site.get("location_precision") or "") == row["precision"]
            )
            if same:
                counts["unchanged"] += 1
                continue

            if site.get("geocode_status") == "manual" and not args.force_manual:
                counts["manual_protected"] += 1
                counts["skipped"] += 1
                continue

            existing_conf = site.get("geocode_confidence")
            if (
                existing_conf is not None
                and site.get("lat") is not None
                and float(existing_conf) > float(row["confidence"])
                and not args.force
            ):
                counts["lower_confidence_skipped"] += 1
                counts["skipped"] += 1
                continue

            if args.dry_run:
                if site.get("lat") is None:
                    counts["inserted"] += 1
                else:
                    counts["updated"] += 1
                continue

            attempted_at = _utc_now()
            had_coords = site.get("lat") is not None and site.get("lng") is not None
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
            if had_coords:
                counts["updated"] += 1
            else:
                counts["inserted"] += 1

    if database_url:
        counts["database_url"] = _sanitize_database_url(database_url)
    args.report_path.parent.mkdir(parents=True, exist_ok=True)
    args.report_path.write_text(json.dumps(counts, ensure_ascii=False, indent=2), encoding="utf-8")
    print(json.dumps(counts, ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
