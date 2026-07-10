from __future__ import annotations

import csv
import hashlib
import json
import os
from collections import Counter
from datetime import datetime, timezone
from pathlib import Path

import pytest
from sqlalchemy import select

from places_service.adapters.outbound.catalog_repository import CatalogSqlRepository
from places_service.adapters.outbound.schema import places_sites
from places_service.cli import import_santander_geocodes
from places_service.domain.models import Entity, ImportRun, LOCATION_PRECISIONS, Site
from places_service.geocoding.bounds import GIRON_BBOX, in_giron_bbox
from places_service.geocoding.geocode_scopes import SANTANDER_SCOPE
from places_service.geocoding.validated_geocode_import import read_csv_rows, validate_rows

CSV_PATH = Path(
    "services/places-service/data/geocodes/santander/geocodes_santander_priorizado_validado.csv"
)
# Canonical hash of the LF-normalized CSV (Windows CRLF copies hash differently).
EXPECTED_SHA256 = "814a59c71899b250362c42a8ffe087cc6d0a7c12d0b3a0f6b1954c27c9cf06d0"
TARGET_GIRON_ID = "cea-giron-centro-de-ensenanza-automovilistica-san--b354b75834"


def _sha256_lf(path: Path) -> str:
    data = path.read_bytes().replace(b"\r\n", b"\n").replace(b"\r", b"\n")
    return hashlib.sha256(data).hexdigest()


def _now() -> str:
    return datetime.now(timezone.utc).isoformat()


def _seed_santander_catalog(db_url: str, *, include_manizales_control: bool = True) -> list[dict[str, str]]:
    rows = read_csv_rows(CSV_PATH)
    repo = CatalogSqlRepository(db_url, create_schema=True)
    now = _now()
    entities: list[Entity] = []
    sites: list[Site] = []

    def add(
        *,
        site_id: str,
        source_place_id: str | None,
        name: str,
        kind: str,
        city: str,
        department: str,
        address: str,
        lat: float | None = None,
        lng: float | None = None,
        is_partner: bool = False,
    ) -> None:
        entity = Entity(
            entity_id=f"ent-{site_id}",
            document_type="NIT",
            document_number=site_id[-8:],
            verification_digit="1",
            document_raw=f"{site_id[-8:]}-1",
            document_valid=True,
            document_validation_status="valid_with_dv",
            legal_name=name,
            legal_name_normalized=name.upper(),
            created_at=now,
            updated_at=now,
        )
        site = Site(
            site_id=site_id,
            entity_id=entity.entity_id,
            actor_type=kind,
            name=name,
            name_normalized=name.upper(),
            address_raw=address,
            address_normalized=address.upper(),
            address_quality="valid",
            department=department,
            municipality=city,
            raw_city=city,
            raw_department=department,
            source_place_id=source_place_id,
            lat=lat,
            lng=lng,
            geocode_status="ok" if lat is not None else "not_attempted",
            location_precision="unknown",
            operational_status="unknown",
            status_verified=False,
            is_partner=is_partner,
            is_bookable=False,
            booking_mode="information_only",
            present_in_latest_snapshot=True,
            source_presence_status="present",
            created_at=now,
            updated_at=now,
        )
        entities.append(entity)
        sites.append(site)

    for i, row in enumerate(rows):
        add(
            site_id=f"site-st-{i:03d}",
            source_place_id=row["id"],
            name=row["name"],
            kind=row["kind"],
            city=row["city"],
            department="Santander",
            address=row["address"],
        )

    if include_manizales_control:
        add(
            site_id="site-mz-control",
            source_place_id="cda-manizales-control-zzzz",
            name="CDA Manizales Control",
            kind="CDA",
            city="Manizales",
            department="Caldas",
            address="Calle 1",
            lat=5.0689,
            lng=-75.5174,
        )

    repo.apply_import(
        import_run=ImportRun(
            import_run_id="seed-santander-batch",
            source_name="test",
            input_filename="seed.json",
            input_sha256="santander-seed",
            started_at=now,
            status="applied",
        ),
        entities=entities,
        sites=sites,
        contacts=[],
        source_records=[],
        duplicate_candidates=[],
    )
    return rows


def test_csv_sha_counts_bbox_and_target_row() -> None:
    assert _sha256_lf(CSV_PATH) == EXPECTED_SHA256

    rows = read_csv_rows(CSV_PATH)
    assert len(rows) == 153
    assert len({r["id"] for r in rows}) == 153
    assert sum(1 for r in rows if not r["lat"].strip() or not r["lng"].strip()) == 0
    assert dict(Counter(r["kind"] for r in rows)) == {"CDA": 37, "CEA": 56, "CIA": 25, "CRC": 35}
    assert dict(Counter(r["city"] for r in rows)) == {
        "Bucaramanga": 81,
        "Floridablanca": 29,
        "Giron": 23,
        "Piedecuesta": 20,
    }
    assert dict(Counter(r["validation_status"] for r in rows)) == {
        "confirmed_business": 65,
        "confirmed_address": 30,
        "approximate_not_confirmed": 58,
    }
    giron = Counter(r["validation_status"] for r in rows if r["city"] == "Giron")
    assert giron["confirmed_business"] == 9
    assert giron["confirmed_address"] == 8
    assert giron["approximate_not_confirmed"] == 6

    target = next(r for r in rows if r["id"] == TARGET_GIRON_ID)
    assert target["lat"] == "7.0689"
    assert target["lng"] == "-73.17018"
    assert target["validation_status"] == "confirmed_address"
    assert target["precision"] == "address_interpolation"
    assert in_giron_bbox(float(target["lat"]), float(target["lng"]))
    assert GIRON_BBOX.contains(float(target["lat"]), float(target["lng"]))

    for precision in {r["precision"] for r in rows}:
        assert precision in LOCATION_PRECISIONS

    valid, errors = validate_rows(rows, SANTANDER_SCOPE)
    assert errors == []
    assert len(valid) == 153


def test_santander_rejects_giron_point_outside_municipal_bbox(tmp_path: Path) -> None:
    rows = read_csv_rows(CSV_PATH)
    bad = dict(rows[0])
    # Force the known wrong-municipality longitude that must not pass Girón bbox.
    target = next(r for r in rows if r["id"] == TARGET_GIRON_ID)
    bad = dict(target)
    bad["lng"] = "-73.1049661"
    bad["validation_status"] = "approximate_not_confirmed"
    path = tmp_path / "bad_giron.csv"
    with path.open("w", encoding="utf-8", newline="") as fh:
        writer = csv.DictWriter(fh, fieldnames=list(rows[0].keys()))
        writer.writeheader()
        for row in rows:
            writer.writerow(bad if row["id"] == TARGET_GIRON_ID else row)
    report = tmp_path / "bad_report.json"
    rc = import_santander_geocodes.main(
        ["--input", str(path), "--dry-run", "--report-path", str(report)]
    )
    assert rc == 1
    payload = json.loads(report.read_text(encoding="utf-8"))
    assert payload["atomic_aborted"] is True
    assert payload["outside_bbox"] >= 1


def test_santander_import_apply_idempotent_and_isolated(tmp_path: Path) -> None:
    db = tmp_path / "st.sqlite"
    db_url = f"sqlite+pysqlite:///{db.as_posix()}"
    _seed_santander_catalog(db_url)
    report_path = tmp_path / "report1.json"

    rc = import_santander_geocodes.main(
        [
            "--input",
            str(CSV_PATH),
            "--apply",
            "--database-url",
            db_url,
            "--report-path",
            str(report_path),
        ]
    )
    assert rc == 0
    report = json.loads(report_path.read_text(encoding="utf-8"))
    assert report["atomic_aborted"] is False
    assert report["scope"] == "santander"
    assert report["by_kind"] == {"CDA": 37, "CEA": 56, "CIA": 25, "CRC": 35}
    assert report["by_validation_status"] == {
        "confirmed_business": 65,
        "confirmed_address": 30,
        "approximate_not_confirmed": 58,
    }
    assert report["inserted"] + report["updated"] == 153
    assert report["resolution"]["source_place_id"] == 153
    assert report["resolution"]["source_records_fallback"] == 0

    repo = CatalogSqlRepository(db_url, create_schema=False)
    with repo.engine.begin() as conn:
        st = conn.execute(
            select(places_sites).where(places_sites.c.department == "Santander")
        ).mappings().all()
        assert len(st) == 153
        assert all(r["lat"] is not None and r["lng"] is not None for r in st)
        assert all(r["geocode_validation_status"] is not None for r in st)
        mz = conn.execute(
            select(places_sites).where(places_sites.c.site_id == "site-mz-control")
        ).mappings().one()
        assert float(mz["lat"]) == pytest.approx(5.0689)
        assert float(mz["lng"]) == pytest.approx(-75.5174)
        assert mz["geocode_validation_status"] is None

        giron_row = conn.execute(
            select(places_sites).where(places_sites.c.source_place_id == TARGET_GIRON_ID)
        ).mappings().one()
        assert float(giron_row["lat"]) == pytest.approx(7.0689)
        assert float(giron_row["lng"]) == pytest.approx(-73.17018)
        assert giron_row["geocode_validation_status"] == "confirmed_address"
        assert giron_row["location_precision"] == "address_interpolation"

    report2 = tmp_path / "report2.json"
    rc2 = import_santander_geocodes.main(
        [
            "--input",
            str(CSV_PATH),
            "--apply",
            "--database-url",
            db_url,
            "--report-path",
            str(report2),
        ]
    )
    assert rc2 == 0
    second = json.loads(report2.read_text(encoding="utf-8"))
    assert second["inserted"] == 0
    assert second["updated"] == 0
    assert second["unchanged"] == 153
    assert second["atomic_aborted"] is False


def test_santander_dry_run_csv_only() -> None:
    rc = import_santander_geocodes.main(
        [
            "--input",
            str(CSV_PATH),
            "--dry-run",
            "--report-path",
            "services/places-service/data/reports/santander_geocode_import_report.json",
        ]
    )
    assert rc == 0


@pytest.mark.skipif(
    not (os.getenv("PLACES_TEST_DATABASE_URL") or "").startswith("postgresql"),
    reason="Set PLACES_TEST_DATABASE_URL=postgresql+... to exercise Postgres apply",
)
def test_santander_apply_postgres(tmp_path: Path) -> None:
    db_url = os.environ["PLACES_TEST_DATABASE_URL"]
    # Use a unique schema-less sqlite-style seed against the provided PG URL.
    # Caller must point at an ephemeral test database.
    _seed_santander_catalog(db_url, include_manizales_control=True)
    report_path = tmp_path / "pg_report.json"
    rc = import_santander_geocodes.main(
        [
            "--input",
            str(CSV_PATH),
            "--apply",
            "--database-url",
            db_url,
            "--report-path",
            str(report_path),
        ]
    )
    assert rc == 0
    report = json.loads(report_path.read_text(encoding="utf-8"))
    assert report["atomic_aborted"] is False
    assert report["inserted"] + report["updated"] == 153
