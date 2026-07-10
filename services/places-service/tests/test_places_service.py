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
            ),
        )
    )

    response = await find_nearest_place(
        FindNearestPlaceRequest(procedure="tecnomecanica", city="Bucaramanga", lat=7.12, lng=-73.12),
        places_repository=repo,
    )

    assert len(response.places) == 1
    assert response.places[0].id == "with-coords"


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
