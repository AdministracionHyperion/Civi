from __future__ import annotations

"""Scope-driven validated geocode import — shared validation + apply core.

City CLIs (Manizales, Santander, …) are thin wrappers around :func:`run_import`
with a :class:`~places_service.geocoding.geocode_scopes.GeocodeScope`.

Design rules (see PLACES_OPERATIONS_RUNBOOK.md):
  * Atomic by default: if ANY row fails validation OR any resolvable row is
    blocked, the whole file is rejected with no writes (exit 1).
  * Resolution is strict: official CSV ``id`` -> ``places_sites.source_place_id``
    (optional ``places_source_records`` fallback for diagnostics only).
    Never fuzzy-match, never create new sites.
  * Per-municipality bbox: each row is checked against the envelope of its CSV
    city — never a widened metro box that would hide wrong-city coordinates.
  * Idempotent: re-applying identical content yields unchanged == rows.
  * Protections are re-checked inside the write transaction.
"""

import csv
import json
import re
from dataclasses import dataclass, field
from datetime import datetime, timezone
from pathlib import Path
from typing import Any
from uuid import uuid4

from sqlalchemy import select

from places_service.adapters.outbound.schema import (
    places_geocode_attempts,
    places_sites,
    places_source_records,
)
from places_service.domain.models import (
    GEOCODE_VALIDATION_STATUSES,
    LOCATION_PRECISIONS,
)
from places_service.geocoding.geocode_scopes import GeocodeScope, fold_place_name

ALLOWED_KINDS = frozenset({"CDA", "CEA", "CIA", "CRC"})

REQUIRED_COLUMNS = frozenset(
    {
        "id",
        "name",
        "address",
        "city",
        "department",
        "country",
        "kind",
        "lat",
        "lng",
        "validation_status",
        "confidence",
        "precision",
        "provider",
    }
)

EVIDENCE_MAX_LEN = 500

EXIT_OK = 0
EXIT_VALIDATION = 1
EXIT_INFRA = 3


@dataclass
class ValidatedGeocode:
    row_number: int
    source_place_id: str
    name: str
    address: str
    city: str
    department: str
    country: str
    kind: str
    lat: float
    lng: float
    validation_status: str
    confidence: float
    precision: str
    provider: str
    nit: str | None = None
    phone: str | None = None
    evidence: str | None = None
    # Populated during DB classification.
    site_id: str | None = None
    resolution_method: str | None = None
    had_coords: bool = False


# Back-compat alias used by Manizales tests / imports.
ManizalesGeocode = ValidatedGeocode


def read_csv_rows(path: Path) -> list[dict[str, str]]:
    """Read the validated CSV as UTF-8 with BOM handling."""
    with path.open(encoding="utf-8-sig", newline="") as handle:
        return list(csv.DictReader(handle))


def _sanitize_evidence(value: str | None, *, max_len: int = EVIDENCE_MAX_LEN) -> str | None:
    if not value:
        return None
    cleaned = re.sub(r"[\x00-\x1f\x7f]", " ", value)
    cleaned = re.sub(r"\s+", " ", cleaned).strip()
    if not cleaned:
        return None
    if len(cleaned) > max_len:
        cleaned = cleaned[: max_len - 1].rstrip() + "\u2026"
    return cleaned


def _outside_bbox_reason(scope: GeocodeScope, city_name: str, lat: float, lng: float) -> str:
    if scope.outside_bbox_prefix:
        return f"{scope.outside_bbox_prefix}:{lat},{lng}"
    return f"outside_municipality_bbox:{city_name}:{lat},{lng}"


def _is_outside_bbox_reason(reason: str) -> bool:
    return reason.startswith("outside_") and "bbox" in reason


def validate_rows(
    raw_rows: list[dict[str, str]],
    scope: GeocodeScope,
) -> tuple[list[ValidatedGeocode], list[dict[str, Any]]]:
    """Validate every row against ``scope``. Returns (valid_rows, errors). Never writes."""
    valid: list[ValidatedGeocode] = []
    errors: list[dict[str, Any]] = []
    seen_ids: set[str] = set()

    for offset, raw in enumerate(raw_rows):
        row_number = offset + 2  # +1 header, +1 to 1-index
        source_place_id = (raw.get("id") or "").strip()
        row_errors: list[str] = []

        if not source_place_id:
            row_errors.append("missing_id")
        elif source_place_id in seen_ids:
            row_errors.append("duplicate_id")
        else:
            seen_ids.add(source_place_id)

        country = (raw.get("country") or "").strip()
        department = (raw.get("department") or "").strip()
        city = (raw.get("city") or "").strip()
        if fold_place_name(country) != fold_place_name(scope.expected_country):
            row_errors.append(f"country_mismatch:{country or '<empty>'}")
        if fold_place_name(department) != fold_place_name(scope.expected_department):
            row_errors.append(f"department_mismatch:{department or '<empty>'}")

        muni = scope.resolve_municipality(city)
        if muni is None:
            allowed = ", ".join(sorted(scope.municipality_names()))
            row_errors.append(f"city_not_in_scope:{city or '<empty>'} (allowed: {allowed})")

        kind = (raw.get("kind") or "").strip().upper()
        if kind not in ALLOWED_KINDS:
            row_errors.append(f"invalid_kind:{kind or '<empty>'}")

        validation_status = (raw.get("validation_status") or "").strip()
        if validation_status not in GEOCODE_VALIDATION_STATUSES:
            row_errors.append(f"invalid_validation_status:{validation_status or '<empty>'}")

        precision = (raw.get("precision") or "").strip()
        if precision not in LOCATION_PRECISIONS:
            row_errors.append(f"invalid_precision:{precision or '<empty>'}")

        provider = (raw.get("provider") or "").strip()
        if not provider:
            row_errors.append("missing_provider")

        lat: float | None = None
        lng: float | None = None
        lat_raw = (raw.get("lat") or "").strip()
        lng_raw = (raw.get("lng") or "").strip()
        try:
            if not lat_raw or not lng_raw:
                raise ValueError("empty")
            lat = float(lat_raw)
            lng = float(lng_raw)
        except (TypeError, ValueError):
            row_errors.append("lat_lng_not_numeric")

        if lat is not None and lng is not None and muni is not None:
            if not muni.bbox.contains(lat, lng):
                row_errors.append(_outside_bbox_reason(scope, muni.name, lat, lng))

        confidence: float | None = None
        try:
            confidence = float((raw.get("confidence") or "").strip())
            if not 0.0 <= confidence <= 1.0:
                row_errors.append(f"confidence_out_of_range:{confidence}")
        except (TypeError, ValueError):
            row_errors.append("confidence_not_numeric")

        if row_errors:
            errors.append(
                {"row": row_number, "id": source_place_id or None, "reasons": row_errors}
            )
            continue

        assert lat is not None and lng is not None and confidence is not None
        valid.append(
            ValidatedGeocode(
                row_number=row_number,
                source_place_id=source_place_id,
                name=(raw.get("name") or "").strip(),
                address=(raw.get("address") or "").strip(),
                city=city,
                department=department,
                country=country,
                kind=kind,
                lat=lat,
                lng=lng,
                validation_status=validation_status,
                confidence=confidence,
                precision=precision,
                provider=provider,
                nit=(raw.get("nit") or "").strip() or None,
                phone=(raw.get("phone") or "").strip() or None,
                evidence=_sanitize_evidence(raw.get("evidence")),
            )
        )

    return valid, errors


def _count_by(values: Any) -> dict[str, int]:
    counts: dict[str, int] = {}
    for value in values:
        key = str(value)
        counts[key] = counts.get(key, 0) + 1
    return counts


def resolve_site_id(
    conn,
    source_place_id: str,
    *,
    use_source_records_fallback: bool = True,
) -> tuple[str | None, str | None]:
    """Resolve official id -> site_id. Never fuzzy. Returns (site_id, method)."""
    hit = conn.execute(
        select(places_sites.c.site_id).where(places_sites.c.source_place_id == source_place_id)
    ).first()
    if hit is not None:
        return str(hit[0]), "source_place_id"

    if use_source_records_fallback:
        candidates = conn.execute(
            select(
                places_source_records.c.matched_site_id,
                places_source_records.c.source_payload,
            ).where(places_source_records.c.source_payload.like(f"%{source_place_id}%"))
        ).all()
        for matched_site_id, payload in candidates:
            if not matched_site_id:
                continue
            try:
                parsed = json.loads(payload)
            except (TypeError, ValueError):
                continue
            if str(parsed.get("id") or "") == source_place_id:
                return str(matched_site_id), "source_records_fallback"

    return None, None


@dataclass
class Classification:
    to_write: list[ValidatedGeocode] = field(default_factory=list)
    blocked: list[dict[str, Any]] = field(default_factory=list)
    unchanged: int = 0
    unknown_ids: list[str] = field(default_factory=list)
    manual_protected: int = 0
    partner_protected: int = 0
    kind_mismatch: int = 0
    municipality_mismatch: int = 0
    resolution: dict[str, int] = field(
        default_factory=lambda: {"source_place_id": 0, "source_records_fallback": 0}
    )


def _same_geocode(site: dict[str, Any], row: ValidatedGeocode) -> bool:
    return (
        site.get("lat") == row.lat
        and site.get("lng") == row.lng
        and float(site.get("geocode_confidence") if site.get("geocode_confidence") is not None else -1)
        == row.confidence
        and str(site.get("geocode_provider") or "") == row.provider
        and str(site.get("location_precision") or "") == row.precision
        and str(site.get("geocode_validation_status") or "") == row.validation_status
        and str(site.get("geocode_status") or "") == "manual"
    )


def _site_municipality_label(site: dict[str, Any]) -> str:
    return str(site.get("municipality") or site.get("raw_city") or "")


def _protection_reason(
    site: dict[str, Any],
    *,
    force_manual: bool,
    force_partner: bool,
) -> str | None:
    has_coords = site.get("lat") is not None and site.get("lng") is not None
    if site.get("geocode_status") == "manual" and has_coords and not force_manual:
        return "manual_protected"
    if bool(site.get("is_partner")) and has_coords and not force_partner:
        return "partner_protected"
    return None


def classify_against_db(
    repo,
    rows: list[ValidatedGeocode],
    scope: GeocodeScope,
    *,
    force_manual: bool,
    force_partner: bool,
    use_source_records_fallback: bool = True,
) -> Classification:
    """DB-aware classification. Does not write. Resolution is strict."""
    result = Classification()
    with repo.engine.connect() as conn:
        for row in rows:
            site_id, method = resolve_site_id(
                conn, row.source_place_id, use_source_records_fallback=use_source_records_fallback
            )
            if site_id is None:
                result.unknown_ids.append(row.source_place_id)
                result.blocked.append(
                    {"row": row.row_number, "id": row.source_place_id, "reason": "unknown_site"}
                )
                continue
            row.site_id = site_id
            row.resolution_method = method
            if method in result.resolution:
                result.resolution[method] += 1

            site = (
                conn.execute(select(places_sites).where(places_sites.c.site_id == site_id))
                .mappings()
                .first()
            )
            if site is None:  # pragma: no cover - resolved id must exist
                result.unknown_ids.append(row.source_place_id)
                result.blocked.append(
                    {"row": row.row_number, "id": row.source_place_id, "reason": "unknown_site"}
                )
                continue

            site_dict = dict(site)
            csv_muni = scope.resolve_municipality(row.city)
            site_muni_label = _site_municipality_label(site_dict)
            site_muni = scope.resolve_municipality(site_muni_label)
            if csv_muni is None or site_muni is None or site_muni.name != csv_muni.name:
                result.municipality_mismatch += 1
                result.blocked.append(
                    {
                        "row": row.row_number,
                        "id": row.source_place_id,
                        "site_id": site_id,
                        "reason": "municipality_mismatch",
                        "csv_city": row.city,
                        "site_municipality": site_muni_label,
                    }
                )
                continue

            site_kind = str(site_dict.get("actor_type") or "").strip().upper()
            if site_kind != row.kind:
                result.kind_mismatch += 1
                result.blocked.append(
                    {
                        "row": row.row_number,
                        "id": row.source_place_id,
                        "site_id": site_id,
                        "reason": "kind_mismatch",
                        "csv_kind": row.kind,
                        "site_kind": site_kind,
                    }
                )
                continue

            if _same_geocode(site_dict, row):
                result.unchanged += 1
                continue

            has_coords = site_dict.get("lat") is not None and site_dict.get("lng") is not None
            row.had_coords = has_coords

            protection = _protection_reason(
                site_dict, force_manual=force_manual, force_partner=force_partner
            )
            if protection == "manual_protected":
                result.manual_protected += 1
                result.blocked.append(
                    {
                        "row": row.row_number,
                        "id": row.source_place_id,
                        "site_id": site_id,
                        "reason": "manual_protected",
                    }
                )
                continue
            if protection == "partner_protected":
                result.partner_protected += 1
                result.blocked.append(
                    {
                        "row": row.row_number,
                        "id": row.source_place_id,
                        "site_id": site_id,
                        "reason": "partner_protected",
                    }
                )
                continue

            result.to_write.append(row)
    return result


class ProtectedSiteError(RuntimeError):
    """Raised when a site becomes protected between classify and write."""


def _write_rows(
    conn,
    rows: list[ValidatedGeocode],
    *,
    now: str,
    attempt_source: str,
    force_manual: bool,
    force_partner: bool,
) -> dict[str, int]:
    counts = {"inserted": 0, "updated": 0}
    for row in rows:
        site = (
            conn.execute(select(places_sites).where(places_sites.c.site_id == row.site_id))
            .mappings()
            .first()
        )
        if site is None:
            raise ProtectedSiteError(f"site disappeared before write: {row.site_id}")
        site_dict = dict(site)
        protection = _protection_reason(
            site_dict, force_manual=force_manual, force_partner=force_partner
        )
        if protection is not None and not _same_geocode(site_dict, row):
            raise ProtectedSiteError(
                f"{protection} re-check failed for {row.source_place_id} ({row.site_id})"
            )

        conn.execute(
            places_sites.update()
            .where(places_sites.c.site_id == row.site_id)
            .values(
                lat=row.lat,
                lng=row.lng,
                geocode_confidence=row.confidence,
                geocode_provider=row.provider,
                geocode_status="manual",
                location_precision=row.precision,
                geocode_validation_status=row.validation_status,
                updated_at=now,
            )
        )
        conn.execute(
            places_geocode_attempts.insert().values(
                attempt_id=str(uuid4()),
                site_id=row.site_id,
                import_run_id=None,
                provider=row.provider,
                query=row.address or None,
                status="manual",
                attempt_number=1,
                lat=row.lat,
                lng=row.lng,
                confidence=row.confidence,
                precision=row.precision,
                response_payload=json.dumps(
                    {
                        "source": attempt_source,
                        "source_place_id": row.source_place_id,
                        "validation_status": row.validation_status,
                        "precision": row.precision,
                        "csv_row": row.row_number,
                        "resolution_method": row.resolution_method,
                        "evidence": row.evidence,
                    },
                    ensure_ascii=False,
                ),
                attempted_at=now,
                completed_at=now,
            )
        )
        if row.had_coords:
            counts["updated"] += 1
        else:
            counts["inserted"] += 1
    return counts


def _sanitize_database_url(url: str) -> str:
    return re.sub(r":([^:@/]+)@", ":***@", url)


def _base_report(
    *,
    mode: str,
    input_path: Path,
    scope: GeocodeScope,
    valid: list[ValidatedGeocode],
    raw_count: int,
) -> dict[str, Any]:
    return {
        "mode": mode,
        "input": str(input_path),
        "scope": scope.key,
        "city": scope.display_name,
        "rows": raw_count,
        "valid_rows": len(valid),
        "inserted": 0,
        "updated": 0,
        "unchanged": 0,
        "skipped": 0,
        "rejected": 0,
        "unknown_site_ids": 0,
        "manual_protected": 0,
        "partner_protected": 0,
        "kind_mismatch": 0,
        "municipality_mismatch": 0,
        "duplicate_ids": 0,
        "outside_bbox": 0,
        "by_kind": _count_by(r.kind for r in valid),
        "by_city": _count_by(r.city for r in valid),
        "by_validation_status": _count_by(r.validation_status for r in valid),
        "atomic_aborted": False,
        "rejected_rows": [],
        "blocked_rows": [],
        "unknown_ids": [],
        "resolution": {"source_place_id": 0, "source_records_fallback": 0},
        "applied_rows": 0,
    }


def run_import(
    *,
    input_path: Path,
    apply: bool,
    database_url: str | None,
    scope: GeocodeScope,
    force_manual: bool = False,
    force_partner: bool = False,
    report_path: Path | None = None,
    use_source_records_fallback: bool = True,
    now: str | None = None,
) -> tuple[int, dict[str, Any]]:
    """Run a scoped validated-geocode import. Returns (exit_code, report)."""
    now = now or datetime.now(timezone.utc).isoformat()
    try:
        raw_rows = read_csv_rows(input_path)
    except OSError as exc:
        report = {
            "mode": "apply" if apply else "dry_run",
            "scope": scope.key,
            "error": f"infra: {exc}",
            "atomic_aborted": True,
        }
        _maybe_write_report(report_path, report)
        return EXIT_INFRA, report

    if not raw_rows or not REQUIRED_COLUMNS.issubset(set(raw_rows[0].keys())):
        missing = REQUIRED_COLUMNS - set(raw_rows[0].keys() if raw_rows else set())
        report = {
            "mode": "apply" if apply else "dry_run",
            "scope": scope.key,
            "error": f"missing required columns: {', '.join(sorted(missing))}",
            "atomic_aborted": True,
        }
        _maybe_write_report(report_path, report)
        return EXIT_VALIDATION, report

    valid, errors = validate_rows(raw_rows, scope)
    mode = "apply" if apply else "dry_run"
    report = _base_report(
        mode=mode, input_path=input_path, scope=scope, valid=valid, raw_count=len(raw_rows)
    )

    report["rejected"] = len(errors)
    report["rejected_rows"] = errors
    report["duplicate_ids"] = sum(
        1 for e in errors if any(r == "duplicate_id" for r in e["reasons"])
    )
    report["outside_bbox"] = sum(
        1 for e in errors if any(_is_outside_bbox_reason(str(r)) for r in e["reasons"])
    )

    if errors:
        report["atomic_aborted"] = True
        _maybe_write_report(report_path, report)
        return EXIT_VALIDATION, report

    if apply and not database_url:
        raise SystemExit(
            "apply requires --database-url or PLACES_DATABASE_URL; "
            "refusing to use an implicit SQLite default"
        )

    if not database_url:
        report["inserted"] = len(valid)
        _maybe_write_report(report_path, report)
        return EXIT_OK, report

    from places_service.adapters.outbound.catalog_repository import CatalogSqlRepository
    from places_service.adapters.outbound.migrate import migrate_schema

    try:
        repo = CatalogSqlRepository(database_url, create_schema=False)
        if apply:
            migrate_schema(repo.engine)
    except Exception as exc:  # noqa: BLE001
        report["atomic_aborted"] = True
        report["error"] = f"infra: {exc}"
        _maybe_write_report(report_path, report)
        return EXIT_INFRA, report

    report["database_url"] = _sanitize_database_url(database_url)

    classification = classify_against_db(
        repo,
        valid,
        scope,
        force_manual=force_manual,
        force_partner=force_partner,
        use_source_records_fallback=use_source_records_fallback,
    )
    report["unchanged"] = classification.unchanged
    report["unknown_site_ids"] = len(classification.unknown_ids)
    report["unknown_ids"] = classification.unknown_ids
    report["manual_protected"] = classification.manual_protected
    report["partner_protected"] = classification.partner_protected
    report["kind_mismatch"] = classification.kind_mismatch
    report["municipality_mismatch"] = classification.municipality_mismatch
    report["skipped"] = len(classification.blocked)
    report["blocked_rows"] = classification.blocked
    report["resolution"] = classification.resolution

    has_blocking = bool(classification.blocked)

    if not apply:
        for row in classification.to_write:
            if row.had_coords:
                report["updated"] += 1
            else:
                report["inserted"] += 1
        if has_blocking:
            report["atomic_aborted"] = True
            _maybe_write_report(report_path, report)
            return EXIT_VALIDATION, report
        _maybe_write_report(report_path, report)
        return EXIT_OK, report

    if has_blocking:
        report["atomic_aborted"] = True
        _maybe_write_report(report_path, report)
        return EXIT_VALIDATION, report

    try:
        with repo.engine.begin() as conn:
            write_counts = _write_rows(
                conn,
                classification.to_write,
                now=now,
                attempt_source=scope.attempt_source,
                force_manual=force_manual,
                force_partner=force_partner,
            )
    except ProtectedSiteError as exc:
        report["atomic_aborted"] = True
        report["error"] = f"protection_recheck: {exc}"
        _maybe_write_report(report_path, report)
        return EXIT_VALIDATION, report
    except Exception as exc:  # noqa: BLE001
        report["atomic_aborted"] = True
        report["error"] = f"infra: {exc}"
        _maybe_write_report(report_path, report)
        return EXIT_INFRA, report

    report["inserted"] = write_counts["inserted"]
    report["updated"] = write_counts["updated"]
    report["applied_rows"] = write_counts["inserted"] + write_counts["updated"]
    _maybe_write_report(report_path, report)
    return EXIT_OK, report


def _maybe_write_report(report_path: Path | None, report: dict[str, Any]) -> None:
    if report_path is None:
        return
    report_path.parent.mkdir(parents=True, exist_ok=True)
    report_path.write_text(json.dumps(report, ensure_ascii=False, indent=2), encoding="utf-8")


__all__ = [
    "ValidatedGeocode",
    "ManizalesGeocode",
    "Classification",
    "ProtectedSiteError",
    "read_csv_rows",
    "validate_rows",
    "resolve_site_id",
    "classify_against_db",
    "run_import",
    "ALLOWED_KINDS",
    "REQUIRED_COLUMNS",
    "EXIT_OK",
    "EXIT_VALIDATION",
    "EXIT_INFRA",
]
