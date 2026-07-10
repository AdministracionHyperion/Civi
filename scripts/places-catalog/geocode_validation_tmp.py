"""Ephemeral local Postgres helper for Manizales geocode dry-run validation.

Requires:
  PLACES_VALIDATION_ADMIN_URL
  PLACES_VALIDATION_DATABASE_URL

Both must target localhost/127.0.0.1. Never production.
"""
from __future__ import annotations

import csv
import json
import os
import re
import sys
from pathlib import Path

from sqlalchemy import create_engine, text

DB_NAME = "civi_geocode_validation_tmp"
REPORT_DIR = Path("services/places-service/data/reports/validation")
MANIZALES_CSV = Path(
    "services/places-service/data/geocodes/manizales/geocodes_manizales_validado.csv"
)


def sanitize(url: str) -> str:
    return re.sub(r":([^:@/]+)@", ":***@", url)


def _env_url(name: str) -> str:
    value = (os.environ.get(name) or "").strip()
    if not value:
        raise SystemExit(f"Missing {name}. Set a local Postgres URL; do not use production.")
    if "localhost" not in value and "127.0.0.1" not in value:
        raise SystemExit(f"{name} must point to localhost/127.0.0.1 (got {sanitize(value)}).")
    return value


def admin_url() -> str:
    return _env_url("PLACES_VALIDATION_ADMIN_URL")


def db_url() -> str:
    return _env_url("PLACES_VALIDATION_DATABASE_URL")


def create_db() -> None:
    engine = create_engine(admin_url(), isolation_level="AUTOCOMMIT", future=True)
    with engine.connect() as conn:
        exists = conn.execute(
            text("select 1 from pg_database where datname = :n"), {"n": DB_NAME}
        ).scalar()
        if exists:
            conn.execute(
                text(
                    "select pg_terminate_backend(pid) from pg_stat_activity "
                    "where datname = :n and pid <> pg_backend_pid()"
                ),
                {"n": DB_NAME},
            )
            conn.execute(text(f'DROP DATABASE "{DB_NAME}"'))
        conn.execute(text(f'CREATE DATABASE "{DB_NAME}"'))
    print(f"created_database={DB_NAME}")
    print(f"database_url={sanitize(db_url())}")


def drop_db() -> None:
    engine = create_engine(admin_url(), isolation_level="AUTOCOMMIT", future=True)
    with engine.connect() as conn:
        conn.execute(
            text(
                "select pg_terminate_backend(pid) from pg_stat_activity "
                "where datname = :n and pid <> pg_backend_pid()"
            ),
            {"n": DB_NAME},
        )
        conn.execute(text(f'DROP DATABASE IF EXISTS "{DB_NAME}"'))
    print(f"dropped_database={DB_NAME}")


def csv_ids(path: Path) -> list[str]:
    with path.open(encoding="utf-8-sig", newline="") as fh:
        return [(row.get("id") or "").strip() for row in csv.DictReader(fh)]


def check_ids(label: str, ids: list[str]) -> dict:
    engine = create_engine(db_url(), future=True)
    missing: list[str] = []
    duplicate: list[str] = []
    found = 0
    with engine.connect() as conn:
        for sid in ids:
            rows = conn.execute(
                text("select site_id from places_sites where source_place_id = :sid"),
                {"sid": sid},
            ).fetchall()
            if len(rows) == 0:
                missing.append(sid)
            elif len(rows) > 1:
                duplicate.append(sid)
                found += 1
            else:
                found += 1
        total_sites = conn.execute(text("select count(*) from places_sites")).scalar()
        with_spid = conn.execute(
            text("select count(*) from places_sites where source_place_id is not null")
        ).scalar()
    return {
        "label": label,
        "csv_ids": len(ids),
        "resolved": found,
        "missing": missing,
        "duplicate_source_place_id": duplicate,
        "places_sites_total": int(total_sites or 0),
        "places_sites_with_source_place_id": int(with_spid or 0),
    }


def write_summary(payload: dict) -> Path:
    REPORT_DIR.mkdir(parents=True, exist_ok=True)
    path = REPORT_DIR / "validation_summary.json"
    path.write_text(json.dumps(payload, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    return path


def main(argv: list[str] | None = None) -> int:
    args = list(sys.argv[1:] if argv is None else argv)
    if not args:
        print("usage: create-db|drop-db|check-manizales|summary")
        return 2
    cmd = args[0]
    if cmd == "create-db":
        create_db()
        return 0
    if cmd == "drop-db":
        drop_db()
        return 0
    if cmd == "check-manizales":
        result = check_ids("manizales", csv_ids(MANIZALES_CSV))
        print(json.dumps(result, ensure_ascii=False, indent=2))
        return 0 if not result["missing"] and not result["duplicate_source_place_id"] else 1
    if cmd == "summary":
        path = write_summary(json.loads(Path(args[1]).read_text(encoding="utf-8")))
        print(path)
        return 0
    raise SystemExit(f"unknown command: {cmd}")


if __name__ == "__main__":
    raise SystemExit(main())
