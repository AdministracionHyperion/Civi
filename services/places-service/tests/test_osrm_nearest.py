"""Unit tests for OSRM table client and GPS re-rank enrichment."""

from __future__ import annotations

from datetime import datetime, timezone
from pathlib import Path

import pytest

from places_service.adapters.outbound import osrm_client
from places_service.adapters.outbound.catalog_repository import CatalogSqlRepository
from places_service.domain.models import Entity, ImportRun, Site


def test_osrm_disabled_returns_none(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.delenv("OSRM_BASE_URL", raising=False)
    osrm_client.clear_cache()
    assert osrm_client.is_enabled() is False
    assert osrm_client.table((5.07, -75.52), [(5.06, -75.51)]) is None


def test_osrm_table_parses_matrix(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("OSRM_BASE_URL", "https://osrm.test")
    osrm_client.clear_cache()

    class _Resp:
        def raise_for_status(self) -> None:
            return None

        def json(self) -> dict:
            return {
                "code": "Ok",
                "distances": [[0.0, 2500.0, 4000.0]],
                "durations": [[0.0, 300.0, 480.0]],
            }

    class _Client:
        def __init__(self, *args, **kwargs) -> None:
            pass

        def __enter__(self):
            return self

        def __exit__(self, *args) -> None:
            return None

        def get(self, url: str, params=None):
            assert "/table/v1/driving/" in url
            return _Resp()

    monkeypatch.setattr(osrm_client.httpx, "Client", _Client)
    result = osrm_client.table((5.07, -75.52), [(5.06, -75.51), (5.05, -75.50)])
    assert result is not None
    assert result[0] == pytest.approx((2.5, 5.0))
    assert result[1] == pytest.approx((4.0, 8.0))


def test_search_nearest_reranks_with_osrm(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("OSRM_BASE_URL", "https://osrm.test")
    osrm_client.clear_cache()

    def fake_table(origin, destinations):
        assert len(destinations) == 2
        # Haversine prefers A; OSRM makes B closer.
        return [(8.0, 12.0), (1.5, 3.0)]

    monkeypatch.setattr(osrm_client, "table", fake_table)

    db_url = f"sqlite+pysqlite:///{(tmp_path / 'osrm_rank.db').as_posix()}"
    repo = CatalogSqlRepository(db_url, create_schema=True)
    now = datetime.now(timezone.utc).isoformat()

    def _entity(eid: str, nit: str, name: str) -> Entity:
        return Entity(
            entity_id=eid,
            document_type="NIT",
            document_number=nit,
            verification_digit="1",
            document_raw=f"{nit}-1",
            document_valid=True,
            document_validation_status="valid_with_dv",
            legal_name=name,
            legal_name_normalized=name.upper(),
            created_at=now,
            updated_at=now,
        )

    def _site(sid: str, eid: str, name: str, lat: float, lng: float) -> Site:
        return Site(
            site_id=sid,
            entity_id=eid,
            actor_type="CDA",
            name=name,
            name_normalized=name.upper(),
            address_raw="Calle 1",
            address_normalized="CALLE 1",
            address_quality="valid",
            department="Santander",
            municipality="Bucaramanga",
            raw_city="Bucaramanga",
            raw_department="Santander",
            municipality_code="68001",
            geocode_status="ok",
            lat=lat,
            lng=lng,
            is_partner=True,
            is_bookable=True,
            booking_mode="civi",
            source_presence_status="present",
            present_in_latest_snapshot=True,
            created_at=now,
            updated_at=now,
        )

    repo.apply_import(
        import_run=ImportRun(
            import_run_id="osrm-test",
            source_name="test",
            input_filename="t.json",
            input_sha256="abc",
            started_at=now,
            status="applied",
        ),
        entities=[
            _entity("ent-a", "9001", "A Near Straight"),
            _entity("ent-b", "9002", "B Far Straight"),
        ],
        sites=[
            _site("site-a", "ent-a", "A Near Straight", 7.1200, -73.1227),
            _site("site-b", "ent-b", "B Far Straight", 7.1300, -73.1227),
        ],
        contacts=[],
        source_records=[],
        duplicate_candidates=[],
    )

    result = repo.search_nearest(
        actor_type="CDA",
        city=None,
        municipality_code=None,
        lat=7.1193,
        lng=-73.1227,
        limit=5,
        radius_km=40,
    )
    ids = [p["id"] for p in result["places"]]
    assert ids[0] == "site-b"
    assert ids[1] == "site-a"
    assert result["places"][0]["distance_source"] == "osrm"
    assert result["places"][0]["distance_km"] == pytest.approx(1.5)
    assert result["places"][0]["duration_min"] == pytest.approx(3.0)
