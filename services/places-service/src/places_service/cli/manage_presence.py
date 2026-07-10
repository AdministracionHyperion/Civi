from __future__ import annotations

import argparse
import json
import os
import re
from datetime import datetime, timezone
from uuid import uuid4

from sqlalchemy import select

from places_service.adapters.outbound.catalog_repository import CatalogSqlRepository
from places_service.adapters.outbound.migrate import migrate_schema
from places_service.adapters.outbound.schema import places_presence_events, places_sites


MIN_TEXT_LEN = 3


def _utc_now() -> str:
    return datetime.now(timezone.utc).isoformat()


def _require_text(value: str | None, *, field: str) -> str:
    text = (value or "").strip()
    if len(text) < MIN_TEXT_LEN:
        raise SystemExit(f"{field} must be at least {MIN_TEXT_LEN} characters")
    return text


def _resolve_database_url(explicit: str | None) -> str:
    database_url = (explicit or os.getenv("PLACES_DATABASE_URL") or "").strip()
    if not database_url:
        raise SystemExit("requires --database-url or PLACES_DATABASE_URL")
    return database_url


def _sanitize_database_url(url: str) -> str:
    return re.sub(r":([^:@/]+)@", ":***@", url)


def preserve_site(
    *,
    database_url: str,
    site_id: str,
    actor: str,
    reason: str,
) -> dict[str, object]:
    repo = CatalogSqlRepository(database_url, create_schema=False)
    migrate_schema(repo.engine)
    now = _utc_now()
    with repo.engine.begin() as conn:
        site = (
            conn.execute(select(places_sites).where(places_sites.c.site_id == site_id))
            .mappings()
            .first()
        )
        if site is None:
            raise SystemExit(f"site not found: {site_id}")

        previous = str(site.get("source_presence_status") or "")
        if previous == "manually_preserved":
            latest = (
                conn.execute(
                    select(places_presence_events)
                    .where(places_presence_events.c.site_id == site_id)
                    .where(places_presence_events.c.event_type == "manually_preserved")
                    .order_by(places_presence_events.c.created_at.desc())
                    .limit(1)
                )
                .mappings()
                .first()
            )
            if (
                latest is not None
                and str(latest.get("actor") or "") == actor
                and str(latest.get("reason") or "") == reason
            ):
                return {
                    "action": "preserve",
                    "site_id": site_id,
                    "idempotent": True,
                    "source_presence_status": "manually_preserved",
                    "database_url": _sanitize_database_url(database_url),
                }

        present_in_snapshot = bool(site.get("present_in_latest_snapshot"))
        update_values: dict[str, object] = {
            "source_presence_status": "manually_preserved",
            "updated_at": now,
        }
        if not present_in_snapshot:
            update_values["present_in_latest_snapshot"] = False

        conn.execute(
            places_sites.update()
            .where(places_sites.c.site_id == site_id)
            .values(**update_values)
        )
        conn.execute(
            places_presence_events.insert().values(
                event_id=str(uuid4()),
                site_id=site_id,
                import_run_id=None,
                previous_status=previous or None,
                new_status="manually_preserved",
                event_type="manually_preserved",
                reason=reason,
                actor=actor,
                source="manual_operation",
                created_at=now,
            )
        )
    return {
        "action": "preserve",
        "site_id": site_id,
        "idempotent": False,
        "previous_status": previous,
        "source_presence_status": "manually_preserved",
        "database_url": _sanitize_database_url(database_url),
    }


def remove_preservation(
    *,
    database_url: str,
    site_id: str,
    actor: str,
    reason: str,
) -> dict[str, object]:
    repo = CatalogSqlRepository(database_url, create_schema=False)
    migrate_schema(repo.engine)
    now = _utc_now()
    with repo.engine.begin() as conn:
        site = (
            conn.execute(select(places_sites).where(places_sites.c.site_id == site_id))
            .mappings()
            .first()
        )
        if site is None:
            raise SystemExit(f"site not found: {site_id}")

        previous = str(site.get("source_presence_status") or "")
        if previous != "manually_preserved":
            return {
                "action": "remove_preservation",
                "site_id": site_id,
                "idempotent": True,
                "source_presence_status": previous,
                "database_url": _sanitize_database_url(database_url),
            }

        present_in_snapshot = bool(site.get("present_in_latest_snapshot"))
        new_status = "present" if present_in_snapshot else "missing"
        values: dict[str, object] = {
            "source_presence_status": new_status,
            "updated_at": now,
        }
        if new_status == "missing":
            values["is_bookable"] = False
            values["booking_mode"] = "unavailable"

        conn.execute(places_sites.update().where(places_sites.c.site_id == site_id).values(**values))
        conn.execute(
            places_presence_events.insert().values(
                event_id=str(uuid4()),
                site_id=site_id,
                import_run_id=None,
                previous_status=previous,
                new_status=new_status,
                event_type="manual_preservation_removed",
                reason=reason,
                actor=actor,
                source="manual_operation",
                created_at=now,
            )
        )
    return {
        "action": "remove_preservation",
        "site_id": site_id,
        "idempotent": False,
        "previous_status": previous,
        "source_presence_status": new_status,
        "database_url": _sanitize_database_url(database_url),
    }


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Manage manually_preserved site presence")
    sub = parser.add_subparsers(dest="command", required=True)

    def add_common(p: argparse.ArgumentParser) -> None:
        p.add_argument("--site-id", required=True)
        p.add_argument("--actor", required=True)
        p.add_argument("--reason", required=True)
        p.add_argument("--database-url", default=None)

    preserve_parser = sub.add_parser("preserve", help="Mark site as manually_preserved")
    add_common(preserve_parser)
    remove_parser = sub.add_parser(
        "remove-preservation", help="Remove manual preservation and restore snapshot presence"
    )
    add_common(remove_parser)

    args = parser.parse_args(argv)
    site_id = _require_text(args.site_id, field="site-id")
    actor = _require_text(args.actor, field="actor")
    reason = _require_text(args.reason, field="reason")
    database_url = _resolve_database_url(args.database_url)

    if args.command == "preserve":
        result = preserve_site(
            database_url=database_url, site_id=site_id, actor=actor, reason=reason
        )
    else:
        result = remove_preservation(
            database_url=database_url, site_id=site_id, actor=actor, reason=reason
        )
    print(json.dumps(result, ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
