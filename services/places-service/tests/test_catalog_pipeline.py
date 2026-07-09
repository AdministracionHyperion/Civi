from __future__ import annotations

import hashlib
import json
from collections import Counter
from pathlib import Path

import pytest

from places_service.adapters.outbound.catalog_repository import CatalogSqlRepository
from places_service.domain.models import ImportRun
from places_service.pipeline.catalog_builder import build_catalog_from_rows
from places_service.pipeline.normalize import (
    compute_nit_verification_digit,
    infer_operational_status,
    normalize_address,
    normalize_document,
    normalize_phone,
)
from places_service.slices.find_nearest_place.schemas import FindNearestPlaceRequest
from places_service.slices.find_nearest_place.use_case import find_nearest_place
from places_service.shared.catalog import Place
from places_service.shared.repository import InMemoryPlacesRepository

ROOT = Path(__file__).resolve().parents[3]
RAW_ORIGINAL = ROOT / "services" / "places-service" / "data" / "raw" / "places_colombia_original.json"
SOURCE_FILE = ROOT / "data" / "places" / "places_colombia_sin_coords.json"


def test_baseline_counts_and_original_preserved() -> None:
    assert RAW_ORIGINAL.exists()
    rows = json.loads(RAW_ORIGINAL.read_text(encoding="utf-8"))
    assert len(rows) == 4107
    counts = Counter(str(r.get("kind") or r.get("actor_type") or "").upper() for r in rows)
    assert counts["CDA"] == 989
    assert counts["CEA"] == 1552
    assert counts["CIA"] == 772
    assert counts["CRC"] == 794

    original_bytes = RAW_ORIGINAL.read_bytes()
    sha = hashlib.sha256(original_bytes).hexdigest()
    assert sha.startswith("457b4fda")
    if SOURCE_FILE.exists():
        assert hashlib.sha256(SOURCE_FILE.read_bytes()).hexdigest() == sha


def test_nit_verification_digit_algorithm() -> None:
    # Official DIAN weights: body 800197268 -> DV 1
    assert compute_nit_verification_digit("800197268") == "1"
    doc = normalize_document("800197268-1")
    assert doc["document_valid"] is True
    assert doc["document_number"] == "800197268"
    assert doc["verification_digit"] == "1"


def test_fake_phones_are_invalid() -> None:
    for fake in ("0", "0000000", "1111111", "1234567", "3000000", "7777777", "9999999"):
        phones = normalize_phone(fake)
        assert phones
        assert phones[0]["is_valid"] is False


def test_city_department_only_address_not_valid() -> None:
    result = normalize_address("Bucaramanga, Santander", city="Bucaramanga", department="Santander")
    assert result["address_quality"] != "valid"
    assert "insufficient_for_geocoding" in result["flags"] or "city_department_only" in result["flags"]


def test_retired_inferred_from_name() -> None:
    status = infer_operational_status("CDA EJEMPLO RETIRADO")
    assert status["operational_status"] == "retired"
    assert status["status_verified"] is False
    assert status["status_inferred_from_name"] is True


def test_build_catalog_reconciliation_and_rules() -> None:
    rows = json.loads(RAW_ORIGINAL.read_text(encoding="utf-8"))
    catalog = build_catalog_from_rows(rows, import_run_id="test-run")
    recon = catalog["reconciliation"]
    assert recon["input_rows"] == 4107
    assert recon["sum_matches_input"] is True
    assert recon["sum_check"] == 4107

    sites = catalog["sites"]
    assert len({s.site_id for s in sites}) == len(sites)

    entities = catalog["entities"]
    doc_keys = [
        (e.document_type, e.document_number)
        for e in entities
        if e.document_number and e.document_type not in {"UNKNOWN", "PROVISIONAL"}
    ]
    assert len(doc_keys) == len(set(doc_keys))

    # Multi-sede: at least one entity with >1 site
    from collections import defaultdict

    by_entity: dict[str, int] = defaultdict(int)
    for site in sites:
        by_entity[site.entity_id] += 1
    assert max(by_entity.values()) > 1

    for site in sites:
        assert site.operational_status != "active" or site.status_verified
        assert site.is_partner is False
        assert site.is_bookable is False
        assert site.booking_mode == "information_only"
        if site.source_actor_id:
            # Must not be a copy of the entity document number alone
            entity = next(e for e in entities if e.entity_id == site.entity_id)
            assert site.source_actor_id != entity.document_number

    retired = [s for s in sites if s.operational_status == "retired"]
    assert retired


@pytest.mark.asyncio
async def test_no_national_fallback_and_empty_city() -> None:
    response = await find_nearest_place(
        FindNearestPlaceRequest(procedure="tecnomecanica", city="MunicipioInexistenteXYZ")
    )
    assert response.places == []
    assert response.no_results_reason == "no_coverage_in_municipality"


@pytest.mark.asyncio
async def test_gps_rejects_outside_colombia() -> None:
    response = await find_nearest_place(
        FindNearestPlaceRequest(procedure="tecnomecanica", lat=40.4, lng=-3.7)
    )
    assert response.places == []
    assert response.no_results_reason == "coordinates_outside_colombia"


@pytest.mark.asyncio
async def test_municipality_search_without_coords_no_invented_distance() -> None:
    repo = InMemoryPlacesRepository(
        (
            Place(
                id="no-coords-muni",
                name="CDA Sin Coords",
                address="Calle 10 # 20-30",
                city="Bucaramanga",
                department="Santander",
                kind="CDA",
                lat=None,
                lng=None,
                status="unknown",
            ),
        )
    )
    response = await find_nearest_place(
        FindNearestPlaceRequest(procedure="tecnomecanica", city="Bucaramanga"),
        places_repository=repo,
    )
    assert len(response.places) == 1
    assert response.places[0].distance_km is None


@pytest.mark.asyncio
async def test_retired_excluded_from_search() -> None:
    repo = InMemoryPlacesRepository(
        (
            Place(
                id="retired-1",
                name="CDA RETIRADO",
                address="Calle 1",
                city="Bucaramanga",
                department="Santander",
                kind="CDA",
                lat=7.12,
                lng=-73.12,
                status="retired",
            ),
            Place(
                id="ok-1",
                name="CDA OK",
                address="Calle 2",
                city="Bucaramanga",
                department="Santander",
                kind="CDA",
                lat=7.13,
                lng=-73.13,
                status="unknown",
            ),
        )
    )
    response = await find_nearest_place(
        FindNearestPlaceRequest(procedure="tecnomecanica", city="Bucaramanga"),
        places_repository=repo,
    )
    assert [p.id for p in response.places] == ["ok-1"]


def test_import_apply_idempotent(tmp_path: Path) -> None:
    rows = json.loads(RAW_ORIGINAL.read_text(encoding="utf-8"))
    # Use a small subset for speed but keep reconciliation logic on full set separately.
    # Full apply is covered by CLI; here we apply full catalog to sqlite for idempotency.
    catalog = build_catalog_from_rows(rows, import_run_id="apply-1")
    db_url = f"sqlite+pysqlite:///{(tmp_path / 'places.sqlite').as_posix()}"
    repo = CatalogSqlRepository(db_url, create_schema=True)
    run = ImportRun(
        import_run_id="apply-1",
        source_name="test",
        input_filename="test.json",
        input_sha256="abc",
        started_at="2026-01-01T00:00:00Z",
        completed_at="2026-01-01T00:00:01Z",
        status="applied",
        source_record_count=4107,
        inserted_count=len(catalog["sites"]),
        updated_count=0,
        unchanged_count=0,
        merged_count=catalog["reconciliation"]["merged_duplicates"],
        rejected_count=0,
        review_count=0,
        report_path=str(tmp_path),
    )
    first = repo.apply_import(
        import_run=run,
        entities=catalog["entities"],
        sites=catalog["sites"],
        contacts=catalog["contacts"],
        source_records=catalog["source_records"],
        duplicate_candidates=catalog["duplicate_candidates"],
    )
    catalog2 = build_catalog_from_rows(rows, import_run_id="apply-2")
    run2 = ImportRun(
        import_run_id="apply-2",
        source_name="test",
        input_filename="test.json",
        input_sha256="abc",
        started_at="2026-01-01T00:00:02Z",
        completed_at="2026-01-01T00:00:03Z",
        status="applied",
        source_record_count=4107,
        inserted_count=len(catalog2["sites"]),
        updated_count=0,
        unchanged_count=0,
        merged_count=catalog2["reconciliation"]["merged_duplicates"],
        rejected_count=0,
        review_count=0,
        report_path=str(tmp_path),
    )
    second = repo.apply_import(
        import_run=run2,
        entities=catalog2["entities"],
        sites=catalog2["sites"],
        contacts=catalog2["contacts"],
        source_records=catalog2["source_records"],
        duplicate_candidates=catalog2["duplicate_candidates"],
    )
    summary = repo.catalog_summary()
    assert summary["unique_sites"] == catalog["reconciliation"]["unique_sites"]
    assert summary["unique_entities"] == catalog["reconciliation"]["unique_entities"]
    assert summary["source_records"] == 4107
    assert first["inserted"] > 0
    # Second apply must not grow source_records / sites (stable IDs + upsert).
    assert summary["unique_sites"] == len({s.site_id for s in catalog2["sites"]})
    assert second["inserted"] == 0
    assert second["updated"] > 0
    # Partner flags preserved: mark one site partner then re-import
    site_id = catalog["sites"][0].site_id
    with repo.engine.begin() as conn:
        from places_service.adapters.outbound.schema import places_sites
        from sqlalchemy import update

        conn.execute(
            update(places_sites)
            .where(places_sites.c.site_id == site_id)
            .values(is_partner=True, is_bookable=True, booking_mode="civi")
        )
    catalog3 = build_catalog_from_rows(rows, import_run_id="apply-3")
    run3 = ImportRun(
        import_run_id="apply-3",
        source_name="test",
        input_filename="test.json",
        input_sha256="abc",
        started_at="2026-01-01T00:00:04Z",
        completed_at="2026-01-01T00:00:05Z",
        status="applied",
        source_record_count=4107,
        inserted_count=0,
        updated_count=0,
        unchanged_count=0,
        merged_count=0,
        rejected_count=0,
        review_count=0,
        report_path=str(tmp_path),
    )
    repo.apply_import(
        import_run=run3,
        entities=catalog3["entities"],
        sites=catalog3["sites"],
        contacts=catalog3["contacts"],
        source_records=catalog3["source_records"],
        duplicate_candidates=catalog3["duplicate_candidates"],
    )
    eligibility = repo.booking_eligibility(site_id)
    assert eligibility["is_partner"] is True
    assert eligibility["is_bookable"] is True
    assert eligibility["booking_mode"] == "civi"


@pytest.mark.asyncio
async def test_booking_eligibility_and_summary_endpoints(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
    from fastapi.testclient import TestClient

    from places_service.main import app

    db = tmp_path / "api.sqlite"
    db_url = f"sqlite+pysqlite:///{db.as_posix()}"
    repo = CatalogSqlRepository(db_url, create_schema=True)
    # seed one bookable site via legacy places + sites
    from places_service.domain.models import Entity, Site
    from datetime import datetime, timezone

    now = datetime.now(timezone.utc).isoformat()
    entity = Entity(
        entity_id="ent-test",
        document_type="NIT",
        document_number="900123456",
        verification_digit="1",
        document_raw="900123456-1",
        document_valid=True,
        legal_name="Test",
        legal_name_normalized="TEST",
        entity_status="unknown",
        created_at=now,
        updated_at=now,
    )
    site = Site(
        site_id="site-bookable",
        entity_id="ent-test",
        actor_type="CDA",
        name="CDA Test",
        name_normalized="CDA TEST",
        address_raw="Calle 1 # 2-3",
        address_normalized="CALLE 1 # 2-3",
        address_quality="valid",
        department="Santander",
        municipality="Bucaramanga",
        raw_city="Bucaramanga",
        raw_department="Santander",
        geocode_status="not_attempted",
        operational_status="unknown",
        status_verified=False,
        is_official_actor=True,
        is_partner=True,
        is_bookable=True,
        booking_mode="civi",
        quality_score=0.8,
        requires_manual_review=False,
        created_at=now,
        updated_at=now,
    )
    run = ImportRun(
        import_run_id="api-1",
        source_name="test",
        input_filename="x",
        input_sha256="x",
        started_at=now,
        completed_at=now,
        status="applied",
        source_record_count=1,
        inserted_count=1,
        updated_count=0,
        unchanged_count=0,
        merged_count=0,
        rejected_count=0,
        review_count=0,
    )
    repo.apply_import(
        import_run=run,
        entities=[entity],
        sites=[site],
        contacts=[],
        source_records=[],
        duplicate_candidates=[],
    )

    monkeypatch.setenv("INTERNAL_SERVICE_TOKEN", "internal-test-token")
    monkeypatch.setenv("PLACES_REPOSITORY_MODE", "sql")
    monkeypatch.setenv("PLACES_DATABASE_URL", db_url)
    monkeypatch.setenv("PLACES_AUTO_CREATE_SCHEMA", "false")
    monkeypatch.setenv("PLACES_BOOTSTRAP_MODE", "none")

    # Re-import module env binding for catalog_repository_from_env
    import places_service.adapters.outbound.catalog_repository as cr

    monkeypatch.setattr(cr, "catalog_repository_from_env", lambda: repo)

    client = TestClient(app)
    headers = {"Authorization": "Bearer internal-test-token"}
    elig = client.get("/internal/places/site-bookable/booking-eligibility", headers=headers)
    assert elig.status_code == 200
    body = elig.json()
    assert body["exists"] is True
    assert body["is_bookable"] is True
    assert body["booking_mode"] == "civi"

    summary = client.get("/internal/places/catalog/summary", headers=headers)
    assert summary.status_code == 200
    assert summary.json()["unique_sites"] >= 1
