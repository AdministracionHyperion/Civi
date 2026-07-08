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
