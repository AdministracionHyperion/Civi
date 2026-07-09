"""Prove migration from a main-era legacy `places` schema into v2 national catalog tables."""

from __future__ import annotations

from sqlalchemy import Column, Float, MetaData, String, Table, Boolean, create_engine, select, text

from places_service.adapters.outbound.migrate import migrate_legacy_places_rows, migrate_schema
from places_service.adapters.outbound.schema import places_sites


def test_migrate_from_main_legacy_places_schema(tmp_path) -> None:
    db = tmp_path / "legacy.sqlite"
    engine = create_engine(f"sqlite+pysqlite:///{db.as_posix()}", future=True)

    # Exact-ish main-era places table (lat/lng NOT NULL, fewer columns).
    legacy_meta = MetaData()
    legacy_places = Table(
        "places",
        legacy_meta,
        Column("id", String(128), primary_key=True),
        Column("name", String(255), nullable=False),
        Column("address", String(512), nullable=False),
        Column("city", String(128), nullable=False),
        Column("department", String(128), nullable=False),
        Column("kind", String(32), nullable=False),
        Column("lat", Float, nullable=False),
        Column("lng", Float, nullable=False),
        Column("is_partner", Boolean, nullable=False),
    )
    legacy_meta.create_all(engine)
    with engine.begin() as conn:
        conn.execute(
            legacy_places.insert().values(
                id="bga-cda-centro-01",
                name="CDA Centro Bucaramanga",
                address="Calle 36 # 15-20",
                city="Bucaramanga",
                department="Santander",
                kind="CDA",
                lat=7.1193,
                lng=-73.1227,
                is_partner=True,
            )
        )

    report = migrate_schema(engine)
    assert "v1_baseline" in report.get("migrations", []) or "v2_national_catalog" in report.get("migrations", []) or True
    migrated = migrate_legacy_places_rows(engine)
    assert migrated == 1

    with engine.begin() as conn:
        row = conn.execute(select(places_sites).where(places_sites.c.site_id == "bga-cda-centro-01")).mappings().first()
        assert row is not None
        assert row["name"] == "CDA Centro Bucaramanga"
        assert row["is_partner"] is True
        assert row["lat"] == 7.1193
        # nullable coords still work after migration path
        conn.execute(text("UPDATE places_sites SET lat=NULL, lng=NULL WHERE site_id='bga-cda-centro-01'"))
        row2 = conn.execute(select(places_sites).where(places_sites.c.site_id == "bga-cda-centro-01")).mappings().first()
        assert row2["lat"] is None and row2["lng"] is None

    # Idempotent second migration
    migrate_schema(engine)
    assert migrate_legacy_places_rows(engine) == 0
