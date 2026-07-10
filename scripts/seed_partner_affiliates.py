#!/usr/bin/env python3
"""Mark a few Santander/Manizales sites as Civi affiliates with ops WhatsApp.

Usage (local docker DB):
  python scripts/seed_partner_affiliates.py \\
    --database-url postgresql+psycopg://civi:civi@localhost:5432/civi \\
    --ops-whatsapp 573001112299

If --site-id is omitted, picks up to 3 present CDA/CIA sites in Bucaramanga/Manizales.
"""
from __future__ import annotations

import argparse
import json
import os
import sys

from sqlalchemy import select

# Allow running from repo root without installing the package in editable mode.
ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
sys.path.insert(0, os.path.join(ROOT, "services", "places-service", "src"))

from places_service.adapters.outbound.catalog_repository import CatalogSqlRepository  # noqa: E402
from places_service.adapters.outbound.migrate import migrate_schema  # noqa: E402
from places_service.adapters.outbound.schema import places_sites  # noqa: E402
from places_service.cli.manage_presence import set_partner  # noqa: E402


PREFERRED_CITIES = ("Bucaramanga", "Floridablanca", "Giron", "Piedecuesta", "Manizales")


def _pick_sites(database_url: str, *, limit: int = 3) -> list[str]:
    repo = CatalogSqlRepository(database_url, create_schema=False)
    migrate_schema(repo.engine)
    with repo.engine.begin() as conn:
        rows = (
            conn.execute(
                select(places_sites.c.site_id, places_sites.c.municipality, places_sites.c.actor_type)
                .where(places_sites.c.actor_type.in_(("CDA", "CIA")))
                .where(places_sites.c.source_presence_status.in_(("present", "reappeared", "manually_preserved")))
                .where(places_sites.c.lat.is_not(None))
                .order_by(places_sites.c.municipality, places_sites.c.name)
            )
            .mappings()
            .all()
        )
    preferred: list[str] = []
    others: list[str] = []
    for row in rows:
        city = str(row["municipality"] or "")
        site_id = str(row["site_id"])
        if any(city.lower() == p.lower() for p in PREFERRED_CITIES):
            preferred.append(site_id)
        else:
            others.append(site_id)
    return (preferred + others)[:limit]


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Seed Civi affiliate partners for booking tests")
    parser.add_argument("--database-url", default=os.getenv("PLACES_DATABASE_URL"))
    parser.add_argument("--ops-whatsapp", required=True, help="E.164 WhatsApp for partner ops (test phone)")
    parser.add_argument("--site-id", action="append", default=[], help="Repeatable site id; auto-picks if omitted")
    parser.add_argument("--limit", type=int, default=3)
    args = parser.parse_args(argv)
    database_url = (args.database_url or "").strip()
    if not database_url:
        raise SystemExit("requires --database-url or PLACES_DATABASE_URL")

    site_ids = list(args.site_id) or _pick_sites(database_url, limit=max(1, args.limit))
    if not site_ids:
        raise SystemExit("no candidate sites found in catalog")

    results = []
    for site_id in site_ids:
        results.append(
            set_partner(
                database_url=database_url,
                site_id=site_id,
                ops_whatsapp=args.ops_whatsapp,
            )
        )
    print(json.dumps({"seeded": results}, ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
