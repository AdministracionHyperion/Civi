from __future__ import annotations

import csv
import json
from pathlib import Path

import pytest

from places_service.adapters.outbound.catalog_repository import CatalogSqlRepository
from places_service.cli import import_geocodes
from places_service.domain.models import Entity, ImportRun, Site


def _seed_site(db_url: str) -> None:
    repo = CatalogSqlRepository(db_url, create_schema=True)
    now = "2026-07-09T00:00:00+00:00"
    entity = Entity(
        entity_id="ent-geo-1",
        document_type="NIT",
        document_number="800197268",
        verification_digit="1",
        document_raw="800197268-1",
        document_valid=True,
        document_validation_status="valid_with_dv",
        legal_name="CDA Geo",
        legal_name_normalized="CDA GEO",
        created_at=now,
        updated_at=now,
    )
    site = Site(
        site_id="site-geo-1",
        entity_id=entity.entity_id,
        actor_type="CDA",
        name="CDA Geo",
        name_normalized="CDA GEO",
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
        created_at=now,
        updated_at=now,
    )
    repo.apply_import(
        import_run=ImportRun(
            import_run_id="seed-geo",
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


def _write_csv(path: Path, rows: list[dict[str, object]]) -> None:
    fieldnames = ["site_id", "lat", "lng", "confidence", "provider", "precision"]
    with path.open("w", encoding="utf-8", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=fieldnames)
        writer.writeheader()
        for row in rows:
            writer.writerow(row)


def test_import_geocodes_apply_requires_database_url(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    csv_path = tmp_path / "geocodes.csv"
    _write_csv(
        csv_path,
        [
            {
                "site_id": "site-geo-1",
                "lat": 7.1193,
                "lng": -73.1227,
                "confidence": 0.9,
                "provider": "manual",
                "precision": "address",
            }
        ],
    )
    monkeypatch.delenv("PLACES_DATABASE_URL", raising=False)
    with pytest.raises(SystemExit) as exc:
        import_geocodes.main(["--input", str(csv_path), "--apply", "--report-path", str(tmp_path / "out.json")])
    assert "refusing to use an implicit SQLite default" in str(exc.value)


def test_import_geocodes_dry_run_without_db(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    csv_path = tmp_path / "geocodes.csv"
    report_path = tmp_path / "geocode_import_report.json"
    _write_csv(
        csv_path,
        [
            {
                "site_id": "site-geo-1",
                "lat": 7.1193,
                "lng": -73.1227,
                "confidence": 0.9,
                "provider": "manual",
                "precision": "address",
            }
        ],
    )
    monkeypatch.delenv("PLACES_DATABASE_URL", raising=False)
    rc = import_geocodes.main(
        ["--input", str(csv_path), "--dry-run", "--report-path", str(report_path)]
    )
    assert rc == 0
    report = json.loads(report_path.read_text(encoding="utf-8"))
    assert report["mode"] == "dry_run"
    assert report["rows"] == 1


def test_import_geocodes_rejects_outside_colombia(tmp_path: Path) -> None:
    db = tmp_path / "geo.sqlite"
    db_url = f"sqlite+pysqlite:///{db.as_posix()}"
    _seed_site(db_url)
    csv_path = tmp_path / "bad.csv"
    report_path = tmp_path / "report.json"
    _write_csv(
        csv_path,
        [
            {
                "site_id": "site-geo-1",
                "lat": 40.0,
                "lng": -74.0,
                "confidence": 0.9,
                "provider": "manual",
                "precision": "address",
            }
        ],
    )
    rc = import_geocodes.main(
        [
            "--input",
            str(csv_path),
            "--apply",
            "--database-url",
            db_url,
            "--report-path",
            str(report_path),
        ]
    )
    assert rc == 0
    report = json.loads(report_path.read_text(encoding="utf-8"))
    assert report["outside_colombia"] == 1
    assert report["rejected"] == 1


def test_import_geocodes_apply_is_idempotent(tmp_path: Path) -> None:
    db = tmp_path / "geo.sqlite"
    db_url = f"sqlite+pysqlite:///{db.as_posix()}"
    _seed_site(db_url)
    csv_path = tmp_path / "ok.csv"
    report1 = tmp_path / "r1.json"
    report2 = tmp_path / "r2.json"
    _write_csv(
        csv_path,
        [
            {
                "site_id": "site-geo-1",
                "lat": 7.1193,
                "lng": -73.1227,
                "confidence": 0.95,
                "provider": "manual_review",
                "precision": "address",
            }
        ],
    )
    assert (
        import_geocodes.main(
            ["--input", str(csv_path), "--apply", "--database-url", db_url, "--report-path", str(report1)]
        )
        == 0
    )
    assert (
        import_geocodes.main(
            ["--input", str(csv_path), "--apply", "--database-url", db_url, "--report-path", str(report2)]
        )
        == 0
    )
    first = json.loads(report1.read_text(encoding="utf-8"))
    second = json.loads(report2.read_text(encoding="utf-8"))
    assert first["inserted"] + first["updated"] >= 1
    assert second["unchanged"] >= 1
    assert second["inserted"] == 0
