from __future__ import annotations

"""CLI: import validated Santander (prioritized metro) geocodes.

    python -m places_service.cli.import_santander_geocodes \
        --input services/places-service/data/geocodes/santander/geocodes_santander_priorizado_validado.csv \
        --dry-run|--apply [--database-url ...]

Strict atomic by default. Resolves by ``source_place_id`` only unless
``--allow-source-records-fallback`` is set (diagnostics). NEVER pass ``--force``
in routine operation. Do not apply in production from this branch without an
explicit ops decision.
"""

import argparse
import json
import os
from pathlib import Path

from places_service.geocoding.geocode_scopes import SANTANDER_SCOPE
from places_service.geocoding.validated_geocode_import import (
    EXIT_INFRA,
    EXIT_VALIDATION,
    run_import,
)


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        description=(
            "Import validated Santander geocodes (atomic, id -> source_place_id; "
            "per-municipality bbox)"
        )
    )
    parser.add_argument("--input", type=Path, default=SANTANDER_SCOPE.default_input)
    mode = parser.add_mutually_exclusive_group(required=True)
    mode.add_argument("--dry-run", action="store_true")
    mode.add_argument("--apply", action="store_true")
    parser.add_argument("--database-url", default=None)
    parser.add_argument(
        "--force",
        action="store_true",
        help="Master override: implies --force-manual and --force-partner. Never use by default.",
    )
    parser.add_argument(
        "--force-manual",
        action="store_true",
        help="Overwrite existing manual geocodes. Never use by default.",
    )
    parser.add_argument(
        "--force-partner",
        action="store_true",
        help="Overwrite coordinates on partner sites. Never use by default.",
    )
    parser.add_argument(
        "--allow-source-records-fallback",
        action="store_true",
        help=(
            "Allow places_source_records fallback when source_place_id is missing. "
            "Routine Santander apply should omit this flag."
        ),
    )
    parser.add_argument("--report-path", type=Path, default=SANTANDER_SCOPE.default_report)
    args = parser.parse_args(argv)

    if not args.input.exists():
        print(f"infra error: input not found: {args.input}")
        return EXIT_INFRA

    database_url = args.database_url or os.getenv("PLACES_DATABASE_URL")

    exit_code, report = run_import(
        input_path=args.input,
        apply=bool(args.apply),
        database_url=database_url,
        scope=SANTANDER_SCOPE,
        force_manual=bool(args.force_manual or args.force),
        force_partner=bool(args.force_partner or args.force),
        report_path=args.report_path,
        use_source_records_fallback=bool(args.allow_source_records_fallback),
    )
    print(json.dumps(report, ensure_ascii=False, indent=2))
    if exit_code == EXIT_VALIDATION:
        print("VALIDATION FAILED: file rejected atomically; no rows written.")
    return exit_code


if __name__ == "__main__":
    raise SystemExit(main())
