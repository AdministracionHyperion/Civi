from __future__ import annotations

from datetime import datetime, timezone

import pytest
from sqlalchemy import select

from places_service.adapters.outbound.catalog_repository import CatalogSqlRepository
from places_service.adapters.outbound.schema import places_presence_events, places_sites
from places_service.cli import manage_presence
from places_service.domain.models import Entity, ImportRun, Site


def _now() -> str:
    return datetime.now(timezone.utc).isoformat()


def _seed(db_url: str, *, present_in_snapshot: bool = True) -> None:
    repo = CatalogSqlRepository(db_url, create_schema=True)
    now = _now()
    entity = Entity(
        entity_id="ent-presence-1",
        document_type="NIT",
        document_number="800197268",
        verification_digit="1",
        document_raw="800197268-1",
        document_valid=True,
        document_validation_status="valid_with_dv",
        legal_name="CDA Presence",
        legal_name_normalized="CDA PRESENCE",
        created_at=now,
        updated_at=now,
    )
    site = Site(
        site_id="site-presence-1",
        entity_id=entity.entity_id,
        actor_type="CDA",
        name="CDA Presence",
        name_normalized="CDA PRESENCE",
        address_raw="Calle 1",
        address_normalized="CALLE 1",
        address_quality="valid",
        department="Santander",
        municipality="Bucaramanga",
        raw_city="Bucaramanga",
        raw_department="Santander",
        municipality_code="68001",
        geocode_status="not_attempted",
        operational_status="unknown",
        status_verified=False,
        is_partner=True,
        is_bookable=True,
        booking_mode="civi",
        present_in_latest_snapshot=present_in_snapshot,
        created_at=now,
        updated_at=now,
    )
    repo.apply_import(
        import_run=ImportRun(
            import_run_id="seed-presence",
            source_name="test",
            input_filename="seed.json",
            input_sha256="abc",
            started_at=now,
            status="applied",
        ),
        entities=[entity],
        sites=[site],
        contacts=[],
        source_records=[],
        duplicate_candidates=[],
    )
    if not present_in_snapshot:
        with repo.engine.begin() as conn:
            conn.execute(
                places_sites.update()
                .where(places_sites.c.site_id == "site-presence-1")
                .values(present_in_latest_snapshot=False, source_presence_status="missing")
            )


def test_preserve_requires_actor_reason_length(tmp_path, monkeypatch: pytest.MonkeyPatch) -> None:
    db = tmp_path / "p.sqlite"
    db_url = f"sqlite+pysqlite:///{db.as_posix()}"
    _seed(db_url)
    monkeypatch.setenv("PLACES_DATABASE_URL", db_url)
    with pytest.raises(SystemExit):
        manage_presence.main(
            ["preserve", "--site-id", "site-presence-1", "--actor", "ab", "--reason", "ok reason"]
        )
    with pytest.raises(SystemExit):
        manage_presence.main(
            ["preserve", "--site-id", "site-presence-1", "--actor", "ops", "--reason", "no"]
        )


def test_preserve_and_idempotent(tmp_path) -> None:
    db = tmp_path / "p.sqlite"
    db_url = f"sqlite+pysqlite:///{db.as_posix()}"
    _seed(db_url)
    rc = manage_presence.main(
        [
            "preserve",
            "--site-id",
            "site-presence-1",
            "--actor",
            "ops-team",
            "--reason",
            "partner request",
            "--database-url",
            db_url,
        ]
    )
    assert rc == 0
    repo = CatalogSqlRepository(db_url, create_schema=False)
    with repo.engine.begin() as conn:
        site = (
            conn.execute(select(places_sites).where(places_sites.c.site_id == "site-presence-1"))
            .mappings()
            .first()
        )
        assert site["source_presence_status"] == "manually_preserved"
        assert site["is_bookable"] is True  # must NOT auto-change
        events = list(
            conn.execute(
                select(places_presence_events).where(
                    places_presence_events.c.event_type == "manually_preserved"
                )
            ).mappings()
        )
        assert len(events) == 1
        assert events[0]["source"] == "manual_operation"
        assert events[0]["actor"] == "ops-team"

    rc2 = manage_presence.main(
        [
            "preserve",
            "--site-id",
            "site-presence-1",
            "--actor",
            "ops-team",
            "--reason",
            "partner request",
            "--database-url",
            db_url,
        ]
    )
    assert rc2 == 0
    with repo.engine.begin() as conn:
        events = list(
            conn.execute(
                select(places_presence_events).where(
                    places_presence_events.c.event_type == "manually_preserved"
                )
            ).mappings()
        )
        assert len(events) == 1


def test_remove_preservation_to_present(tmp_path) -> None:
    db = tmp_path / "p.sqlite"
    db_url = f"sqlite+pysqlite:///{db.as_posix()}"
    _seed(db_url, present_in_snapshot=True)
    manage_presence.main(
        [
            "preserve",
            "--site-id",
            "site-presence-1",
            "--actor",
            "ops-team",
            "--reason",
            "keep visible",
            "--database-url",
            db_url,
        ]
    )
    rc = manage_presence.main(
        [
            "remove-preservation",
            "--site-id",
            "site-presence-1",
            "--actor",
            "ops-team",
            "--reason",
            "snapshot ok",
            "--database-url",
            db_url,
        ]
    )
    assert rc == 0
    repo = CatalogSqlRepository(db_url, create_schema=False)
    with repo.engine.begin() as conn:
        site = (
            conn.execute(select(places_sites).where(places_sites.c.site_id == "site-presence-1"))
            .mappings()
            .first()
        )
        assert site["source_presence_status"] == "present"
        assert site["is_bookable"] is True
        events = list(
            conn.execute(
                select(places_presence_events).where(
                    places_presence_events.c.event_type == "manual_preservation_removed"
                )
            ).mappings()
        )
        assert len(events) == 1
        assert events[0]["source"] == "manual_operation"
        assert events[0]["new_status"] == "present"


def test_remove_preservation_to_missing_disables_booking(tmp_path) -> None:
    db = tmp_path / "p.sqlite"
    db_url = f"sqlite+pysqlite:///{db.as_posix()}"
    _seed(db_url, present_in_snapshot=False)
    # Force manually_preserved while snapshot says missing
    repo = CatalogSqlRepository(db_url, create_schema=False)
    with repo.engine.begin() as conn:
        conn.execute(
            places_sites.update()
            .where(places_sites.c.site_id == "site-presence-1")
            .values(source_presence_status="manually_preserved", is_bookable=True, booking_mode="civi")
        )
    rc = manage_presence.main(
        [
            "remove-preservation",
            "--site-id",
            "site-presence-1",
            "--actor",
            "ops-team",
            "--reason",
            "no longer needed",
            "--database-url",
            db_url,
        ]
    )
    assert rc == 0
    with repo.engine.begin() as conn:
        site = (
            conn.execute(select(places_sites).where(places_sites.c.site_id == "site-presence-1"))
            .mappings()
            .first()
        )
        assert site["source_presence_status"] == "missing"
        assert site["is_bookable"] is False
        assert site["booking_mode"] == "unavailable"
        events = list(
            conn.execute(
                select(places_presence_events).where(
                    places_presence_events.c.event_type == "manual_preservation_removed"
                )
            ).mappings()
        )
        assert len(events) == 1
        assert events[0]["new_status"] == "missing"
