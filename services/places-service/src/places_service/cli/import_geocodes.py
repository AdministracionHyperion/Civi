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

EXIT_OK = 0
EXIT_VALIDATION = 1
EXIT_PARTIAL = 2
EXIT_INFRA = 3


def _utc_now() -> str:
    return datetime.now(timezone.utc).isoformat()


def _sanitize_database_url(url: str) -> str:
    return re.sub(r":([^:@/]+)@", ":***@", url)


def _empty_counts(mode: str) -> dict[str, object]:
    return {
        "mode": mode,
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
        "atomic_aborted": False,
        "allow_partial": False,
        "applied_rows": 0,
    }


def _parse_rows(rows: list[dict[str, str]]) -> tuple[list[dict[str, object]], dict[str, object]]:
    counts = _empty_counts("parse")
    validated: list[dict[str, object]] = []
    seen_ids: set[str] = set()
    for row_number, row in enumerate(rows, start=2):
        counts["rows"] = int(counts["rows"]) + 1
        site_id = str(row.get("site_id") or "").strip()
        provider = str(row.get("provider") or "").strip()
        precision = str(row.get("precision") or "").strip().lower()
        try:
            if not site_id:
                raise ValueError("site_id empty")
            if site_id in seen_ids:
                counts["duplicate_site_ids"] = int(counts["duplicate_site_ids"]) + 1
                counts["rejected"] = int(counts["rejected"]) + 1
                counts["rejected_rows"].append({"row": row_number, "site_id": site_id, "reason": "duplicate_site_id"})  # type: ignore[union-attr]
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
                counts["outside_colombia"] = int(counts["outside_colombia"]) + 1
                counts["rejected"] = int(counts["rejected"]) + 1
                counts["rejected_rows"].append(  # type: ignore[union-attr]
                    {"row": row_number, "site_id": site_id, "reason": "outside_colombia"}
                )
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
            counts["rejected"] = int(counts["rejected"]) + 1
            counts["rejected_rows"].append(  # type: ignore[union-attr]
                {"row": row_number, "site_id": site_id or None, "reason": str(exc)}
            )
    return validated, counts


def _classify_against_db(
    *,
    repo: CatalogSqlRepository,
    validated: list[dict[str, object]],
    counts: dict[str, object],
    force: bool,
    force_manual: bool,
) -> tuple[list[dict[str, object]], list[dict[str, object]]]:
    """Return (to_write, blocked) after DB-aware validation. Does not write."""
    to_write: list[dict[str, object]] = []
    blocked: list[dict[str, object]] = []
    with repo.engine.connect() as conn:
        for row in validated:
            site_id = str(row["site_id"])
            site = (
                conn.execute(select(places_sites).where(places_sites.c.site_id == site_id))
                .mappings()
                .first()
            )
            if site is None:
                counts["unknown_site_ids"] = int(counts["unknown_site_ids"]) + 1
                counts["unknown_ids"].append(site_id)  # type: ignore[union-attr]
                counts["rejected"] = int(counts["rejected"]) + 1
                counts["rejected_rows"].append(  # type: ignore[union-attr]
                    {"row": row["row_number"], "site_id": site_id, "reason": "unknown_site"}
                )
                blocked.append({**row, "block_reason": "unknown_site"})
                continue

            same = (
                site.get("lat") == row["lat"]
                and site.get("lng") == row["lng"]
                and float(site.get("geocode_confidence") or -1) == float(row["confidence"])  # type: ignore[arg-type]
                and str(site.get("geocode_provider") or "") == row["provider"]
                and str(site.get("location_precision") or "") == row["precision"]
            )
            if same:
                counts["unchanged"] = int(counts["unchanged"]) + 1
                continue

            if site.get("geocode_status") == "manual" and not force_manual:
                counts["manual_protected"] = int(counts["manual_protected"]) + 1
                counts["skipped"] = int(counts["skipped"]) + 1
                counts["rejected_rows"].append(  # type: ignore[union-attr]
                    {"row": row["row_number"], "site_id": site_id, "reason": "manual_protected"}
                )
                blocked.append({**row, "block_reason": "manual_protected"})
                continue

            existing_conf = site.get("geocode_confidence")
            if (
                existing_conf is not None
                and site.get("lat") is not None
                and float(existing_conf) > float(row["confidence"])  # type: ignore[arg-type]
                and not force
            ):
                counts["lower_confidence_skipped"] = int(counts["lower_confidence_skipped"]) + 1
                counts["skipped"] = int(counts["skipped"]) + 1
                counts["rejected_rows"].append(  # type: ignore[union-attr]
                    {"row": row["row_number"], "site_id": site_id, "reason": "lower_confidence"}
                )
                blocked.append({**row, "block_reason": "lower_confidence"})
                continue

            to_write.append({**row, "_had_coords": site.get("lat") is not None and site.get("lng") is not None})
    return to_write, blocked


def _write_rows(conn, rows: list[dict[str, object]], counts: dict[str, object]) -> None:
    for row in rows:
        site_id = str(row["site_id"])
        attempted_at = _utc_now()
        had_coords = bool(row.get("_had_coords"))
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
                attempt_number=1,
                lat=row["lat"],
                lng=row["lng"],
                confidence=row["confidence"],
                precision=row["precision"],
                response_payload=json.dumps({"csv_row": row["row_number"]}),
                attempted_at=attempted_at,
                completed_at=attempted_at,
            )
        )
        if had_coords:
            counts["updated"] = int(counts["updated"]) + 1
        else:
            counts["inserted"] = int(counts["inserted"]) + 1
        counts["applied_rows"] = int(counts["applied_rows"]) + 1


def _write_report(path: Path, counts: dict[str, object]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(counts, ensure_ascii=False, indent=2), encoding="utf-8")
    print(json.dumps(counts, ensure_ascii=False, indent=2))


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
        "--allow-partial",
        action="store_true",
        help="Apply valid rows and skip/reject others (exit 2). Default is strict atomic abort.",
    )
    parser.add_argument(
        "--report-path",
        type=Path,
        default=Path("services/places-service/data/reports/geocode_import_report.json"),
    )
    args = parser.parse_args(argv)

    try:
        with args.input.open(encoding="utf-8", newline="") as handle:
            rows = list(csv.DictReader(handle))
    except OSError as exc:
        print(f"infra error reading input: {exc}", file=__import__("sys").stderr)
        return EXIT_INFRA

    required = {"site_id", "lat", "lng", "confidence", "provider", "precision"}
    if not rows or not required.issubset(set(rows[0].keys())):
        parser.error(f"CSV must include columns: {', '.join(sorted(required))}")

    validated, counts = _parse_rows(rows)
    counts["mode"] = "dry_run" if args.dry_run else "apply"
    counts["allow_partial"] = bool(args.allow_partial)

    database_url = args.database_url or os.getenv("PLACES_DATABASE_URL")
    if args.apply and not database_url:
        raise SystemExit(
            "apply requires --database-url or PLACES_DATABASE_URL; "
            "refusing to use an implicit SQLite default"
        )

    # CSV-level validation failures (outside_colombia, bad fields, duplicates)
    csv_has_errors = int(counts["rejected"]) > 0

    repo = None
    if database_url:
        try:
            repo = CatalogSqlRepository(database_url, create_schema=False)
            if args.apply:
                migrate_schema(repo.engine)
        except Exception as exc:  # noqa: BLE001
            counts["atomic_aborted"] = True
            counts["error"] = f"infra: {exc}"
            _write_report(args.report_path, counts)
            return EXIT_INFRA

    if args.dry_run and repo is None:
        # No DB: only CSV validation. Strict: any rejected → exit 1.
        if csv_has_errors and not args.allow_partial:
            counts["atomic_aborted"] = True
            _write_report(args.report_path, counts)
            return EXIT_VALIDATION
        if csv_has_errors and args.allow_partial:
            _write_report(args.report_path, counts)
            return EXIT_PARTIAL
        # dry-run success: count would-be inserts as inserted for report friendliness
        counts["inserted"] = len(validated)
        _write_report(args.report_path, counts)
        return EXIT_OK

    assert repo is not None
    if database_url:
        counts["database_url"] = _sanitize_database_url(database_url)

    to_write, blocked = _classify_against_db(
        repo=repo,
        validated=validated,
        counts=counts,
        force=args.force,
        force_manual=args.force_manual,
    )

    has_blocking = csv_has_errors or bool(blocked)

    if args.dry_run:
        for row in to_write:
            if row.get("_had_coords"):
                counts["updated"] = int(counts["updated"]) + 1
            else:
                counts["inserted"] = int(counts["inserted"]) + 1
        if has_blocking and not args.allow_partial:
            counts["atomic_aborted"] = True
            _write_report(args.report_path, counts)
            return EXIT_VALIDATION
        if has_blocking and args.allow_partial:
            _write_report(args.report_path, counts)
            return EXIT_PARTIAL
        _write_report(args.report_path, counts)
        return EXIT_OK

    # APPLY path
    if has_blocking and not args.allow_partial:
        counts["atomic_aborted"] = True
        # Ensure no writes happened
        counts["inserted"] = 0
        counts["updated"] = 0
        counts["applied_rows"] = 0
        _write_report(args.report_path, counts)
        return EXIT_VALIDATION

    try:
        with repo.engine.begin() as conn:
            _write_rows(conn, to_write, counts)
    except Exception as exc:  # noqa: BLE001
        counts["atomic_aborted"] = True
        counts["error"] = f"infra: {exc}"
        counts["inserted"] = 0
        counts["updated"] = 0
        counts["applied_rows"] = 0
        _write_report(args.report_path, counts)
        return EXIT_INFRA

    if has_blocking and args.allow_partial:
        _write_report(args.report_path, counts)
        return EXIT_PARTIAL

    _write_report(args.report_path, counts)
    return EXIT_OK


if __name__ == "__main__":
    raise SystemExit(main())
