"""Ephemeral local Postgres helper for Manizales/Santander geocode dry-run validation.

Requires environment variables (never commit real credentials):

  PLACES_VALIDATION_ADMIN_URL   e.g. postgresql+psycopg://USER:PASS@localhost:5432/postgres
  PLACES_VALIDATION_DATABASE_URL  e.g. postgresql+psycopg://USER:PASS@localhost:5432/civi_geocode_validation_tmp

Creates/drops an isolated database named ``civi_geocode_validation_tmp``.
Does not touch production. Geocode CLIs must still be invoked separately with ``--dry-run``.
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
SANTANDER_CSV = Path(
    "services/places-service/data/geocodes/santander/geocodes_santander_priorizado_validado.csv"
)


def sanitize(url: str) -> str:
    return re.sub(r":([^:@/]+)@", ":***@", url)


def _env_url(name: str) -> str:
    value = (os.environ.get(name) or "").strip()
    if not value:
        raise SystemExit(
            f"Missing {name}. Set a local Postgres URL; do not use production."
        )
    if "localhost" not in value and "127.0.0.1" not in value:
        raise SystemExit(
            f"{name} must point to localhost/127.0.0.1 for this helper "
            f"(got host from {sanitize(value)})."
        )
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
        null_spid = conn.execute(
            text("select count(*) from places_sites where source_place_id is null")
        ).scalar()
    result = {
        "label": label,
        "required": len(ids),
        "found_exact_one": found - len(duplicate),
        "missing_count": len(missing),
        "duplicate_count": len(duplicate),
        "missing_ids": missing,
        "duplicate_ids": duplicate,
        "catalog_places_sites": int(total_sites or 0),
        "catalog_with_source_place_id": int(with_spid or 0),
        "catalog_null_source_place_id": int(null_spid or 0),
    }
    print(json.dumps(result, ensure_ascii=False, indent=2))
    return result


def count_geocode_status() -> dict:
    engine = create_engine(db_url(), future=True)
    with engine.connect() as conn:
        return {
            "sites_with_lat": int(
                conn.execute(text("select count(*) from places_sites where lat is not null")).scalar()
                or 0
            ),
            "sites_with_validation": int(
                conn.execute(
                    text(
                        "select count(*) from places_sites "
                        "where geocode_validation_status is not null"
                    )
                ).scalar()
                or 0
            ),
            "geocode_attempts": int(
                conn.execute(text("select count(*) from places_geocode_attempts")).scalar() or 0
            ),
        }


def migrate() -> None:
    from places_service.adapters.outbound.migrate import migrate_schema
    from sqlalchemy import inspect

    engine = create_engine(db_url(), future=True)
    migrate_schema(engine)
    insp = inspect(engine)
    cols = {c["name"] for c in insp.get_columns("places_sites")}
    needed = {"source_place_id", "geocode_validation_status"}
    print(
        json.dumps(
            {
                "migrate_ok": needed.issubset(cols),
                "has_source_place_id": "source_place_id" in cols,
                "has_geocode_validation_status": "geocode_validation_status" in cols,
                "tables": sorted(insp.get_table_names()),
            },
            indent=2,
        )
    )


if __name__ == "__main__":
    cmd = sys.argv[1] if len(sys.argv) > 1 else ""
    if cmd == "create":
        create_db()
    elif cmd == "drop":
        drop_db()
    elif cmd == "migrate":
        migrate()
    elif cmd == "check-manizales":
        check_ids("manizales", csv_ids(MANIZALES_CSV))
    elif cmd == "check-santander":
        check_ids("santander", csv_ids(SANTANDER_CSV))
    elif cmd == "snapshot":
        print(json.dumps(count_geocode_status(), indent=2))
    else:
        raise SystemExit(
            "usage: create|drop|migrate|check-manizales|check-santander|snapshot"
        )
