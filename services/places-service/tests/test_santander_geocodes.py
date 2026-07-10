from __future__ import annotations

import csv
import hashlib
import json
import os
import uuid
from collections import Counter
from datetime import datetime, timezone
from pathlib import Path
from urllib.parse import urlparse, urlunparse

import pytest
from sqlalchemy import create_engine, select, text

from places_service.adapters.outbound.catalog_repository import (
    CatalogSqlRepository,
    _site_to_place_result,
)
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

DEFAULT_PG_ADMIN_URL = "postgresql+psycopg://civi:civi@localhost:5432/postgres"


def _sha256_lf(path: Path) -> str:
    data = path.read_bytes().replace(b"\r\n", b"\n").replace(b"\r", b"\n")
    return hashlib.sha256(data).hexdigest()


def _now() -> str:
    return datetime.now(timezone.utc).isoformat()


def _write_csv(path: Path, rows: list[dict[str, str]]) -> None:
    with path.open("w", encoding="utf-8", newline="") as fh:
        writer = csv.DictWriter(fh, fieldnames=list(rows[0].keys()))
        writer.writeheader()
        for row in rows:
            writer.writerow(row)


def _seed_santander_catalog(
    db_url: str,
    *,
    include_manizales_control: bool = True,
    rows: list[dict[str, str]] | None = None,
) -> list[dict[str, str]]:
    rows = rows if rows is not None else read_csv_rows(CSV_PATH)
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
        geocode_status: str | None = None,
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
        resolved_status = geocode_status or ("ok" if lat is not None else "not_attempted")
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
            geocode_status=resolved_status,
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
            import_run_id=f"seed-santander-{uuid.uuid4().hex[:8]}",
            source_name="test",
            input_filename="seed.json",
            input_sha256=f"santander-seed-{uuid.uuid4().hex[:8]}",
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


def _ephemeral_postgres_url() -> tuple[str, str, object]:
    """Create an ephemeral Postgres database. Returns (db_url, db_name, admin_engine)."""
    admin_url = (
        os.getenv("PLACES_TEST_DATABASE_URL")
        or os.getenv("PLACES_DATABASE_URL")
        or DEFAULT_PG_ADMIN_URL
    )
    if not admin_url.startswith("postgresql"):
        raise RuntimeError(f"Postgres admin URL required, got: {admin_url}")

    parsed = urlparse(admin_url)
    # Always connect to the maintenance DB for CREATE/DROP DATABASE.
    admin_parsed = parsed._replace(path="/postgres")
    admin_engine = create_engine(urlunparse(admin_parsed), isolation_level="AUTOCOMMIT", future=True)
    db_name = f"santander_gc_{uuid.uuid4().hex[:10]}"
    with admin_engine.connect() as conn:
        conn.execute(text(f'CREATE DATABASE "{db_name}"'))
    db_url = urlunparse(parsed._replace(path=f"/{db_name}"))
    return db_url, db_name, admin_engine


def _drop_postgres_db(admin_engine, db_name: str) -> None:
    with admin_engine.connect() as conn:
        conn.execute(
            text(
                "SELECT pg_terminate_backend(pid) FROM pg_stat_activity "
                "WHERE datname = :name AND pid <> pg_backend_pid()"
            ),
            {"name": db_name},
        )
        conn.execute(text(f'DROP DATABASE IF EXISTS "{db_name}"'))


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
    assert SANTANDER_SCOPE.expected_counts is not None
    assert SANTANDER_SCOPE.expected_counts.total == 153


def test_santander_rejects_giron_point_outside_municipal_bbox(tmp_path: Path) -> None:
    rows = read_csv_rows(CSV_PATH)
    path = tmp_path / "bad_giron.csv"
    mutated = []
    for row in rows:
        if row["id"] == TARGET_GIRON_ID:
            bad = dict(row)
            bad["lng"] = "-73.1049661"
            bad["validation_status"] = "approximate_not_confirmed"
            mutated.append(bad)
        else:
            mutated.append(row)
    _write_csv(path, mutated)
    report = tmp_path / "bad_report.json"
    rc = import_santander_geocodes.main(
        ["--input", str(path), "--dry-run", "--report-path", str(report)]
    )
    assert rc == 1
    payload = json.loads(report.read_text(encoding="utf-8"))
    assert payload["atomic_aborted"] is True
    assert payload["outside_bbox"] >= 1


def test_santander_rejects_truncated_or_wrong_counts(tmp_path: Path) -> None:
    rows = read_csv_rows(CSV_PATH)
    truncated = rows[:-1]
    path = tmp_path / "truncated.csv"
    _write_csv(path, truncated)
    report = tmp_path / "truncated_report.json"
    rc = import_santander_geocodes.main(
        ["--input", str(path), "--dry-run", "--report-path", str(report)]
    )
    assert rc == 1
    payload = json.loads(report.read_text(encoding="utf-8"))
    assert payload["atomic_aborted"] is True
    assert payload["count_mismatch"] is True
    assert any("expected_total:153" in r for r in payload["count_mismatch_reasons"])


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


def test_duplicate_source_place_id_aborts(tmp_path: Path) -> None:
    db = tmp_path / "dup.sqlite"
    db_url = f"sqlite+pysqlite:///{db.as_posix()}"
    rows = _seed_santander_catalog(db_url)
    target = rows[0]["id"]
    repo = CatalogSqlRepository(db_url, create_schema=False)
    with repo.engine.begin() as conn:
        original = (
            conn.execute(select(places_sites).where(places_sites.c.source_place_id == target))
            .mappings()
            .one()
        )
        payload = dict(original)
        payload["site_id"] = "site-dup-extra"
        payload["name"] = "DUP"
        payload["name_normalized"] = "DUP"
        conn.execute(places_sites.insert().values(**payload))
    report = tmp_path / "dup_report.json"
    rc = import_santander_geocodes.main(
        [
            "--input",
            str(CSV_PATH),
            "--apply",
            "--database-url",
            db_url,
            "--report-path",
            str(report),
        ]
    )
    assert rc == 1
    payload = json.loads(report.read_text(encoding="utf-8"))
    assert payload["atomic_aborted"] is True
    assert payload["duplicate_source_place_id"] >= 1
    assert any(b["reason"] == "duplicate_source_place_id" for b in payload["blocked_rows"])


def test_department_mismatch_aborts(tmp_path: Path) -> None:
    db = tmp_path / "dept.sqlite"
    db_url = f"sqlite+pysqlite:///{db.as_posix()}"
    _seed_santander_catalog(db_url)
    repo = CatalogSqlRepository(db_url, create_schema=False)
    with repo.engine.begin() as conn:
        conn.execute(
            places_sites.update()
            .where(places_sites.c.source_place_id == TARGET_GIRON_ID)
            .values(department="Cundinamarca", raw_department="Cundinamarca")
        )
    report = tmp_path / "dept_report.json"
    rc = import_santander_geocodes.main(
        ["--input", str(CSV_PATH), "--apply", "--database-url", db_url, "--report-path", str(report)]
    )
    assert rc == 1
    payload = json.loads(report.read_text(encoding="utf-8"))
    assert payload["department_mismatch"] >= 1
    assert any(b["reason"] == "department_mismatch" for b in payload["blocked_rows"])


def test_municipality_mismatch_aborts(tmp_path: Path) -> None:
    db = tmp_path / "muni.sqlite"
    db_url = f"sqlite+pysqlite:///{db.as_posix()}"
    _seed_santander_catalog(db_url)
    repo = CatalogSqlRepository(db_url, create_schema=False)
    with repo.engine.begin() as conn:
        conn.execute(
            places_sites.update()
            .where(places_sites.c.source_place_id == TARGET_GIRON_ID)
            .values(municipality="Bucaramanga", raw_city="Bucaramanga")
        )
    report = tmp_path / "muni_report.json"
    rc = import_santander_geocodes.main(
        ["--input", str(CSV_PATH), "--apply", "--database-url", db_url, "--report-path", str(report)]
    )
    assert rc == 1
    payload = json.loads(report.read_text(encoding="utf-8"))
    assert payload["municipality_mismatch"] >= 1


def test_kind_mismatch_aborts(tmp_path: Path) -> None:
    db = tmp_path / "kind.sqlite"
    db_url = f"sqlite+pysqlite:///{db.as_posix()}"
    _seed_santander_catalog(db_url)
    repo = CatalogSqlRepository(db_url, create_schema=False)
    with repo.engine.begin() as conn:
        conn.execute(
            places_sites.update()
            .where(places_sites.c.source_place_id == TARGET_GIRON_ID)
            .values(actor_type="CDA")
        )
    report = tmp_path / "kind_report.json"
    rc = import_santander_geocodes.main(
        ["--input", str(CSV_PATH), "--apply", "--database-url", db_url, "--report-path", str(report)]
    )
    assert rc == 1
    payload = json.loads(report.read_text(encoding="utf-8"))
    assert payload["kind_mismatch"] >= 1


def test_manual_and_partner_protections_abort(tmp_path: Path) -> None:
    rows = read_csv_rows(CSV_PATH)
    manual_id = rows[0]["id"]
    partner_id = rows[1]["id"]

    db = tmp_path / "prot.sqlite"
    db_url = f"sqlite+pysqlite:///{db.as_posix()}"
    _seed_santander_catalog(db_url)
    repo = CatalogSqlRepository(db_url, create_schema=False)
    with repo.engine.begin() as conn:
        conn.execute(
            places_sites.update()
            .where(places_sites.c.source_place_id == manual_id)
            .values(lat=7.12, lng=-73.12, geocode_status="manual")
        )
        conn.execute(
            places_sites.update()
            .where(places_sites.c.source_place_id == partner_id)
            .values(lat=7.12, lng=-73.12, is_partner=True, geocode_status="ok")
        )

    report = tmp_path / "prot_report.json"
    rc = import_santander_geocodes.main(
        ["--input", str(CSV_PATH), "--apply", "--database-url", db_url, "--report-path", str(report)]
    )
    assert rc == 1
    payload = json.loads(report.read_text(encoding="utf-8"))
    assert payload["manual_protected"] >= 1
    assert payload["partner_protected"] >= 1
    reasons = {b["reason"] for b in payload["blocked_rows"]}
    assert "manual_protected" in reasons
    assert "partner_protected" in reasons


def test_geojson_counts_and_approximate_not_confirmed(tmp_path: Path) -> None:
    db = tmp_path / "geo.sqlite"
    db_url = f"sqlite+pysqlite:///{db.as_posix()}"
    _seed_santander_catalog(db_url)
    assert (
        import_santander_geocodes.main(
            [
                "--input",
                str(CSV_PATH),
                "--apply",
                "--database-url",
                db_url,
                "--report-path",
                str(tmp_path / "geo_report.json"),
            ]
        )
        == 0
    )
    repo = CatalogSqlRepository(db_url, create_schema=False)
    counts = {
        city: len(repo.list_geojson_features(city=city, department="Santander"))
        for city in ("Bucaramanga", "Floridablanca", "Giron", "Piedecuesta")
    }
    assert counts == {"Bucaramanga": 81, "Floridablanca": 29, "Giron": 23, "Piedecuesta": 20}

    all_features = []
    for city in counts:
        all_features.extend(repo.list_geojson_features(city=city, department="Santander"))
    approx = [
        f for f in all_features if f["properties"]["validation_status"] == "approximate_not_confirmed"
    ]
    assert len(approx) == 58
    assert all(f["properties"]["location_confirmed"] is False for f in approx)


def test_nearest_exposes_geocode_fields(tmp_path: Path) -> None:
    db = tmp_path / "near.sqlite"
    db_url = f"sqlite+pysqlite:///{db.as_posix()}"
    _seed_santander_catalog(db_url)
    assert (
        import_santander_geocodes.main(
            [
                "--input",
                str(CSV_PATH),
                "--apply",
                "--database-url",
                db_url,
                "--report-path",
                str(tmp_path / "near_report.json"),
            ]
        )
        == 0
    )
    repo = CatalogSqlRepository(db_url, create_schema=False)
    result = repo.search_nearest(
        actor_type=None,
        city=None,
        municipality_code=None,
        lat=7.1193,
        lng=-73.1227,
        limit=5,
        radius_km=25.0,
    )
    assert result["places"]
    place = result["places"][0]
    assert place["lat"] is not None
    assert place["lng"] is not None
    assert place["validation_status"] in {
        "confirmed_business",
        "confirmed_address",
        "approximate_not_confirmed",
    }
    assert "location_confirmed" in place
    assert place["precision"] == place["location_precision"]
    if place["validation_status"] == "approximate_not_confirmed":
        assert place["location_confirmed"] is False
    else:
        assert place["location_confirmed"] is True

    # Mapping helper stays consistent with PlaceResult geocode surface.
    with repo.engine.begin() as conn:
        row = (
            conn.execute(
                select(places_sites).where(
                    places_sites.c.geocode_validation_status == "approximate_not_confirmed"
                )
            )
            .mappings()
            .first()
        )
    mapped = _site_to_place_result(dict(row))
    assert mapped["location_confirmed"] is False
    assert mapped["validation_status"] == "approximate_not_confirmed"


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


def test_santander_apply_postgres_ephemeral(tmp_path: Path) -> None:
    try:
        db_url, db_name, admin_engine = _ephemeral_postgres_url()
    except Exception as exc:  # noqa: BLE001
        pytest.fail(
            "PostgreSQL efímero requerido para cerrar el PR. "
            f"No se pudo crear la base ({exc}). "
            "Define PLACES_TEST_DATABASE_URL o levanta Postgres en localhost:5432 "
            f"(default {DEFAULT_PG_ADMIN_URL})."
        )

    try:
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
        assert report["resolution"]["source_place_id"] == 153

        # Idempotent second apply on the same ephemeral DB.
        report2 = tmp_path / "pg_report2.json"
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
        assert second["unchanged"] == 153
        print(f"postgres_ephemeral_ok database={db_name} applied=153 unchanged=153")
    finally:
        try:
            _drop_postgres_db(admin_engine, db_name)
        except Exception:  # noqa: BLE001
            pass
        admin_engine.dispose()
