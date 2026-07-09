"""Restore a prior catalog snapshot while recalculating site presence.

The command delegates to the normal catalog importer, so a restore creates a
new import run, marks snapshot sites present, marks absent sites missing, and
preserves existing partner and booking flags.
"""

from __future__ import annotations

import argparse

from places_service.cli import import_catalog


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        description="Restore a catalog snapshot using normal import lifecycle semantics"
    )
    parser.add_argument("--input", required=True)
    mode = parser.add_mutually_exclusive_group(required=True)
    mode.add_argument("--apply", action="store_true")
    mode.add_argument("--dry-run", action="store_true")
    parser.add_argument("--database-url", default=None)
    parser.add_argument("--report-dir", default=None)
    parser.add_argument("--source-updated-at", default=None)
    args = parser.parse_args(argv)

    importer_args = ["--input", args.input, "--apply" if args.apply else "--dry-run"]
    if args.database_url:
        importer_args.extend(("--database-url", args.database_url))
    if args.report_dir:
        importer_args.extend(("--report-dir", args.report_dir))
    if args.source_updated_at:
        importer_args.extend(("--source-updated-at", args.source_updated_at))
    return import_catalog.main(importer_args)


if __name__ == "__main__":
    raise SystemExit(main())
