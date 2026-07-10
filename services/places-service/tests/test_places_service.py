import pytest
from fastapi.testclient import TestClient

from places_service.adapters.outbound.sql_repository import SqlPlacesRepository
from places_service.main import app
from places_service.slices.find_nearest_place.schemas import FindNearestPlaceRequest
from places_service.slices.find_nearest_place.use_case import find_nearest_place
from places_service.slices.list_partners.use_case import list_partners


@pytest.mark.asyncio
async def test_find_nearest_place_by_city_and_procedure() -> None:
    response = await find_nearest_place(
        FindNearestPlaceRequest(procedure="tecnomecanica", city="Bucaramanga")
    )

    assert response.success
    assert response.places
    assert response.places[0].kind == "CDA"
    assert response.places[0].city == "Bucaramanga"


@pytest.mark.asyncio
async def test_list_partners_omits_phone_data() -> None:
    response = await list_partners()

    assert response.partners
    assert not hasattr(response.partners[0], "phone")


@pytest.mark.asyncio
async def test_find_nearest_place_uses_sql_repository_seeded_from_catalog() -> None:
    repo = SqlPlacesRepository("sqlite+pysqlite:///:memory:", create_schema=True, seed_catalog=True)

    response = await find_nearest_place(
        FindNearestPlaceRequest(procedure="curso_multa", city="Bucaramanga"),
        places_repository=repo,
    )

    assert response.places
    assert response.places[0].kind == "CIA"
    assert response.places[0].city == "Bucaramanga"


def test_sql_places_repository_lists_partners_without_phone_data() -> None:
    repo = SqlPlacesRepository("sqlite+pysqlite:///:memory:", create_schema=True, seed_catalog=True)

    partners = repo.list_partners()

    assert partners
    assert all(partner.is_partner for partner in partners)


@pytest.mark.asyncio
async def test_find_nearest_skips_places_without_coordinates() -> None:
    from places_service.shared.catalog import Place
    from places_service.shared.repository import InMemoryPlacesRepository

    repo = InMemoryPlacesRepository(
        (
            Place(
                id="no-coords",
                name="CDA Sin Coords",
                address="Calle 1",
                city="Bucaramanga",
                department="Santander",
                kind="CDA",
                lat=None,
                lng=None,
                geocode_status="skipped",
            ),
            Place(
                id="with-coords",
                name="CDA Con Coords",
                address="Calle 2",
                city="Bucaramanga",
                department="Santander",
                kind="CDA",
                lat=7.12,
                lng=-73.12,
                geocode_status="ok",
                is_partner=True,
                is_bookable=True,
                booking_mode="civi",
                phone="573001112200",
            ),
        )
    )

    response = await find_nearest_place(
        FindNearestPlaceRequest(procedure="tecnomecanica", city="Bucaramanga", lat=7.12, lng=-73.12),
        places_repository=repo,
    )

    assert len(response.places) == 1
    assert response.places[0].id == "with-coords"
    assert response.places[0].is_partner is True
    assert response.places[0].contact_available is True


@pytest.mark.asyncio
async def test_find_nearest_excludes_non_affiliates(tmp_path) -> None:
    from places_service.shared.catalog import Place
    from places_service.shared.repository import InMemoryPlacesRepository

    repo = InMemoryPlacesRepository(
        (
            Place(
                id="non-partner",
                name="CDA Publico",
                address="Calle 1",
                city="Bucaramanga",
                department="Santander",
                kind="CDA",
                lat=7.12,
                lng=-73.12,
                is_partner=False,
                is_bookable=False,
                booking_mode="information_only",
            ),
            Place(
                id="partner",
                name="CDA Afiliado",
                address="Calle 2",
                city="Bucaramanga",
                department="Santander",
                kind="CDA",
                lat=7.121,
                lng=-73.121,
                is_partner=True,
                is_bookable=True,
                booking_mode="civi",
                phone="573001112201",
            ),
        )
    )
    response = await find_nearest_place(
        FindNearestPlaceRequest(procedure="tecnomecanica", city="Bucaramanga", lat=7.12, lng=-73.12),
        places_repository=repo,
    )
    assert [p.id for p in response.places] == ["partner"]


def test_set_partner_and_ops_contact(tmp_path) -> None:
    from datetime import datetime, timezone

    from places_service.adapters.outbound.catalog_repository import CatalogSqlRepository
    from places_service.cli import manage_presence
    from places_service.domain.models import Entity, ImportRun, Site

    db = tmp_path / "partners-ops.sqlite"
    database_url = f"sqlite+pysqlite:///{db.as_posix()}"
    repo = CatalogSqlRepository(database_url, create_schema=True)
    now = datetime.now(timezone.utc).isoformat()
    entity = Entity(
        entity_id="ent-ops-1",
        document_type="NIT",
        document_number="800197268",
        verification_digit="1",
        document_raw="800197268-1",
        document_valid=True,
        document_validation_status="valid_with_dv",
        legal_name="CDA Ops",
        legal_name_normalized="CDA OPS",
        created_at=now,
        updated_at=now,
    )
    site = Site(
        site_id="site-ops-1",
        entity_id="ent-ops-1",
        actor_type="CDA",
        name="CDA Ops Present",
        name_normalized="CDA OPS PRESENT",
        address_raw="Calle 36 # 15-20",
        address_normalized="CALLE 36 # 15-20",
        address_quality="valid",
        department="Santander",
        municipality="Bucaramanga",
        raw_city="Bucaramanga",
        raw_department="Santander",
        municipality_code="68001",
        geocode_status="ok",
        lat=7.12,
        lng=-73.12,
        operational_status="unknown",
        status_verified=False,
        is_partner=False,
        is_bookable=False,
        booking_mode="information_only",
        source_presence_status="present",
        present_in_latest_snapshot=True,
        created_at=now,
        updated_at=now,
    )
    repo.apply_import(
        import_run=ImportRun(
            import_run_id="run-ops-1",
            source_name="test",
            input_filename="a.json",
            input_sha256="a",
            started_at=now,
            status="applied",
        ),
        entities=[entity],
        sites=[site],
        contacts=[],
        source_records=[],
        duplicate_candidates=[],
    )

    rc = manage_presence.main(
        [
            "set-partner",
            "--site-id",
            "site-ops-1",
            "--ops-whatsapp",
            "+57 300 111 2299",
            "--database-url",
            database_url,
        ]
    )
    assert rc == 0
    contact = repo.get_ops_contact("site-ops-1")
    assert contact is not None
    assert contact["e164"] == "573001112299"
    lookup = repo.lookup_by_ops_whatsapp("573001112299")
    assert lookup is not None
    assert lookup["site_id"] == "site-ops-1"

    nearest = repo.search_nearest(
        actor_type="CDA",
        city="Bucaramanga",
        municipality_code=None,
        lat=7.12,
        lng=-73.12,
        limit=5,
        radius_km=40,
    )
    assert nearest["places"]
    assert nearest["places"][0]["id"] == "site-ops-1"
    assert nearest["places"][0]["contact_available"] is True
    assert nearest["places"][0]["is_partner"] is True


def test_sql_places_repository_upserts_by_id() -> None:
    from places_service.shared.catalog import Place

    repo = SqlPlacesRepository("sqlite+pysqlite:///:memory:", create_schema=True, seed_catalog=False)
    first = Place(
        id="cda-test-01",
        name="CDA Test",
        address="Calle 1",
        city="Bucaramanga",
        department="Santander",
        kind="CDA",
        lat=None,
        lng=None,
        phone="300",
        source="runt",
        geocode_status="skipped",
        nit="900",
    )
    updated = Place(
        id="cda-test-01",
        name="CDA Test Actualizado",
        address="Calle 2",
        city="Bucaramanga",
        department="Santander",
        kind="CDA",
        lat=None,
        lng=None,
        phone="301",
        source="runt",
        geocode_status="skipped",
        nit="900",
    )

    assert repo.upsert_places([first]) == 1
    assert repo.upsert_places([updated]) == 1
    places = repo.list_all()
    assert len(places) == 1
    assert places[0].name == "CDA Test Actualizado"
    assert places[0].phone == "301"


def test_places_internal_partners_requires_token(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("INTERNAL_SERVICE_TOKEN", "internal-test-token")
    client = TestClient(app)

    assert client.get("/internal/places/partners").status_code == 401

    response = client.get(
        "/internal/places/partners",
        headers={"Authorization": "Bearer internal-test-token"},
    )
    assert response.status_code == 200
    assert response.json()["partners"]
