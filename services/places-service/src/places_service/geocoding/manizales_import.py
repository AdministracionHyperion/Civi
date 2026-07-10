from __future__ import annotations

"""Validated Manizales geocode import — thin wrapper over the shared engine.

Prefer importing from ``places_service.geocoding.validated_geocode_import`` for new
callers. This module keeps the historical Manizales API surface stable.
"""

from pathlib import Path
from typing import Any

from places_service.geocoding.geocode_scopes import MANIZALES_SCOPE
from places_service.geocoding.validated_geocode_import import (
    ALLOWED_KINDS,
    EXIT_INFRA,
    EXIT_OK,
    EXIT_VALIDATION,
    Classification,
    ManizalesGeocode,
    ValidatedGeocode,
    classify_against_db as _classify_against_db,
    read_csv_rows,
    resolve_site_id,
    run_import as _run_import,
    validate_rows as _validate_rows,
)

EXPECTED_COUNTRY = MANIZALES_SCOPE.expected_country
EXPECTED_DEPARTMENT = MANIZALES_SCOPE.expected_department
EXPECTED_CITY = "manizales"


def validate_rows(
    raw_rows: list[dict[str, str]],
) -> tuple[list[ValidatedGeocode], list[dict[str, Any]]]:
    return _validate_rows(raw_rows, MANIZALES_SCOPE)


def classify_against_db(
    repo,
    rows: list[ValidatedGeocode],
    *,
    force_manual: bool,
    force_partner: bool,
    use_source_records_fallback: bool = True,
) -> Classification:
    return _classify_against_db(
        repo,
        rows,
        MANIZALES_SCOPE,
        force_manual=force_manual,
        force_partner=force_partner,
        use_source_records_fallback=use_source_records_fallback,
    )


def run_import(
    *,
    input_path: Path,
    apply: bool,
    database_url: str | None,
    force_manual: bool = False,
    force_partner: bool = False,
    report_path: Path | None = None,
    use_source_records_fallback: bool = True,
    now: str | None = None,
) -> tuple[int, dict[str, Any]]:
    return _run_import(
        input_path=input_path,
        apply=apply,
        database_url=database_url,
        scope=MANIZALES_SCOPE,
        force_manual=force_manual,
        force_partner=force_partner,
        report_path=report_path,
        use_source_records_fallback=use_source_records_fallback,
        now=now,
    )


__all__ = [
    "ManizalesGeocode",
    "ValidatedGeocode",
    "Classification",
    "read_csv_rows",
    "validate_rows",
    "resolve_site_id",
    "classify_against_db",
    "run_import",
    "ALLOWED_KINDS",
    "EXPECTED_COUNTRY",
    "EXPECTED_DEPARTMENT",
    "EXPECTED_CITY",
    "EXIT_OK",
    "EXIT_VALIDATION",
    "EXIT_INFRA",
]
