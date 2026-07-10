from __future__ import annotations

from datetime import datetime, timezone

from sqlalchemy import select

from places_service.adapters.outbound.catalog_repository import CatalogSqlRepository
from places_service.adapters.outbound.schema import places_presence_events
from places_service.domain.models import Entity, ImportRun, Site


def _now() -> str:
    return datetime.now(timezone.utc).isoformat()


def _entity() -> Entity:
    now = _now()
    return Entity(
        entity_id="ent-partner-1",
        document_type="NIT",
        document_number="800197268",
        verification_digit="1",
        document_raw="800197268-1",
        document_valid=True,
        document_validation_status="valid_with_dv",
        legal_name="CDA Partner",
        legal_name_normalized="CDA PARTNER",
        created_at=now,
        updated_at=now,
    )


def _site(*, site_id: str, is_partner: bool = True) -> Site:
    now = _now()
    return Site(
        site_id=site_id,
        entity_id="ent-partner-1",
        actor_type="CDA",
        name="CDA Partner Present",
        name_normalized="CDA PARTNER PRESENT",
        address_raw="Calle 36 # 15-20",
        address_normalized="CALLE 36 # 15-20",
        address_quality="valid",
        department="Santander",
        municipality="Bucaramanga",
        raw_city="Bucaramanga",
        raw_department="Santander",
        municipality_code="68001",
        geocode_status="not_attempted",
        operational_status="unknown",
        status_verified=False,
        is_partner=is_partner,
        is_bookable=is_partner,
        booking_mode="civi" if is_partner else "information_only",
        created_at=now,
        updated_at=now,
    )


def test_missing_partner_excluded_from_list_partners(tmp_path) -> None:
    db = tmp_path / "partners.sqlite"
    repo = CatalogSqlRepository(f"sqlite+pysqlite:///{db.as_posix()}", create_schema=True)
    now = _now()
    entity = _entity()
    present = _site(site_id="site-partner-present", is_partner=True)
    will_go_missing = _site(site_id="site-partner-missing", is_partner=True)

    first = repo.apply_import(
        import_run=ImportRun(
            import_run_id="run-1",
            source_name="test",
            input_filename="a.json",
            input_sha256="a",
            started_at=now,
            status="applied",
        ),
        entities=[entity],
        sites=[present, will_go_missing],
        contacts=[],
        source_records=[],
        duplicate_candidates=[],
    )
    assert first["inserted"] == 2

    partners = repo.list_partners()
    assert {p["id"] for p in partners} == {"site-partner-present", "site-partner-missing"}

    second = repo.apply_import(
        import_run=ImportRun(
            import_run_id="run-2",
            source_name="test",
            input_filename="b.json",
            input_sha256="b",
            started_at=now,
            status="applied",
        ),
        entities=[entity],
        sites=[present],
        contacts=[],
        source_records=[],
        duplicate_candidates=[],
    )
    assert second["missing"] == 1

    partners_after = repo.list_partners()
    assert [p["id"] for p in partners_after] == ["site-partner-present"]

    with repo.engine.begin() as conn:
        events = [
            dict(row)
            for row in conn.execute(
                select(places_presence_events).order_by(places_presence_events.c.created_at)
            ).mappings()
        ]
    event_types = {(e["site_id"], e["event_type"]) for e in events}
    assert ("site-partner-present", "first_seen") in event_types
    assert ("site-partner-missing", "first_seen") in event_types
    assert ("site-partner-missing", "missing") in event_types
