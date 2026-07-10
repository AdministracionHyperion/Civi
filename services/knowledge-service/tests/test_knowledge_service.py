import pytest
from fastapi.testclient import TestClient

from knowledge_service.main import app
from knowledge_service.slices.get_city_info.schemas import GetCityInfoRequest
from knowledge_service.slices.get_city_info.use_case import get_city_info
from knowledge_service.slices.get_domain_info.schemas import GetDomainInfoRequest
from knowledge_service.slices.get_domain_info.use_case import get_domain_info


@pytest.mark.asyncio
async def test_get_tecnomecanica_info() -> None:
    response = await get_domain_info(GetDomainInfoRequest(domain="tecnomecanica", topic="que_llevar"))

    assert response.success
    assert response.domain == "tecnomecanica"
    assert response.body
    assert "SOAT" in response.body


@pytest.mark.asyncio
async def test_get_cia_info() -> None:
    response = await get_domain_info(GetDomainInfoRequest(domain="cia", topic="descuentos_fotomulta"))

    assert response.success
    assert response.domain == "cia"
    assert response.body
    assert "50%" in response.body


@pytest.mark.asyncio
async def test_get_city_info_for_enabled_city() -> None:
    response = await get_city_info(GetCityInfoRequest(city="Bogota"))

    assert response.success
    assert response.enabled
    assert response.city == "Bogota"
    assert response.total_places >= 1


@pytest.mark.asyncio
async def test_get_city_info_for_unsupported_city_lists_options() -> None:
    response = await get_city_info(GetCityInfoRequest(city="Cali"))

    assert response.success
    assert not response.enabled
    assert "Bogota" in response.nearby_cities


def test_knowledge_internal_info_requires_token(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("INTERNAL_SERVICE_TOKEN", "internal-test-token")
    client = TestClient(app)

    payload = {"domain": "tecnomecanica", "topic": "duracion"}
    assert client.post("/internal/knowledge/info", json=payload).status_code == 401

    response = client.post(
        "/internal/knowledge/info",
        json=payload,
        headers={"Authorization": "Bearer internal-test-token"},
    )
    assert response.status_code == 200
    assert response.json()["success"] is True


@pytest.mark.parametrize(
    ("query", "expected_token"),
    [
        ("que pasa si me paso un semaforo en rojo", "semaforo"),
        ("que cubre el SOAT en un accidente", "soat"),
        ("choque simple sin heridos que debo hacer", "accidente"),
        ("puedo circular con pico y placa si tengo cita medica", "pico"),
    ],
)
def test_search_corpus_finds_relevant_chunks(query: str, expected_token: str) -> None:
    from knowledge_service.shared.search import search_corpus

    hits = search_corpus(query=query, limit=5)
    assert hits
    joined = " ".join(f"{hit.title} {hit.body} {hit.domain}".lower() for hit in hits)
    assert expected_token in joined


def test_knowledge_internal_search_endpoint(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("INTERNAL_SERVICE_TOKEN", "internal-test-token")
    client = TestClient(app)

    payload = {"query": "descuentos CIA fotomulta", "limit": 3}
    assert client.post("/internal/knowledge/search", json=payload).status_code == 401

    response = client.post(
        "/internal/knowledge/search",
        json=payload,
        headers={"Authorization": "Bearer internal-test-token"},
    )
    assert response.status_code == 200
    body = response.json()
    assert body["success"] is True
    assert body["hits"]
    assert "score" in body["hits"][0]
