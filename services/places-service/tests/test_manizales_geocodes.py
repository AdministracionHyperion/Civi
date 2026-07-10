from __future__ import annotations

import csv
from collections import Counter
from datetime import datetime, timezone
from pathlib import Path

import pytest
from sqlalchemy import select, text

from places_service.adapters.outbound.catalog_repository import (
    CatalogSqlRepository,
    _site_to_place_result,
)
from places_service.adapters.outbound.schema import places_sites
from places_service.cli import import_manizales_geocodes
from places_service.domain.models import Entity, ImportRun, Site
from places_service.geocoding.bounds import MANIZALES_BBOX, in_manizales_bbox
from places_service.geocoding.colombia_address import normalize_colombia_address
from places_service.geocoding.manizales_import import read_csv_rows, validate_rows
from places_service.geocoding.scoring import accepts_centroid_as_business, score_name

CSV_PATH = Path("services/places-service/data/geocodes/manizales/geocodes_manizales_validado.csv")

EXACT_CONFIRMED = {
    "cda-manizales-cda-caldas-el-bosque-a730920403": (5.0619543, -75.5239713, 46.1),
    "cda-manizales-centro-de-diagnostico-automotor-motolina-0ce021ad5c": (
        5.0668747,
        -75.5108309,
        41.5,
    ),
    "cea-manizales-centro-de-ensenanza-automovilistica-cald-3e6c3b1930": (
        5.0627826,
        -75.4962432,
        33.1,
    ),
    "cia-manizales-centro-integral-de-atencion-rutas-de-col-e89cbc963e": (
        5.0694094,
        -75.5181173,
        31.6,
    ),
    "cea-manizales-academia-automovilistica-caldas-sas-12d613c393": (
        5.0627089,
        -75.4949577,
        33.6,
    ),
}

INTERPOLATED_APPROX = {
    "cea-manizales-academia-automovilistica-piloto-177f760536": (5.0680434, -75.5217931, 41.2),
    "cea-manizales-cea-practicar-del-eje-manizales-71a9a35cf0": (5.0518489, -75.4840936, 868.7),
    "cia-manizales-centro-integral-de-atencion-eje-cafetero-3000df8047": (
        5.0692235,
        -75.5179797,
        15.8,
    ),
}


UNCHANGED_APPROX = {
    "cda-manizales-cda-socicar-7acac31f0f": (5.0694483, -75.5235525),
    "crc-manizales-centro-de-reconocimiento-de-conductores--dfb8fe156d": (
        5.0702978,
        -75.5177831,
    ),
    "crc-manizales-certificamos-agustinos-98839ab670": (5.069385, -75.5203143),
    "cia-manizales-cimyc-manizales-s-a-s-498175000a": (5.05813485, -75.48422695),
}


def _now() -> str:
    return datetime.now(timezone.utc).isoformat()


def _seed_manizales_catalog(db_url: str) -> list[dict[str, str]]:
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
            site_id=f"site-mz-{i:02d}",
            source_place_id=row["id"],
            name=row["name"],
            kind=row["kind"],
            city="Manizales",
            department="Caldas",
            address=row["address"],
        )
    add(
        site_id="site-bga-01",
        source_place_id="cda-bucaramanga-control-aaaa",
        name="CDA Bucaramanga Control",
        kind="CDA",
        city="Bucaramanga",
        department="Santander",
        address="Calle 36",
        lat=7.1193,
        lng=-73.1227,
    )
    add(
        site_id="site-bga-02",
        source_place_id="cea-floridablanca-control-bbbb",
        name="CEA Floridablanca Control",
        kind="CEA",
        city="Floridablanca",
        department="Santander",
        address="Calle 10",
        lat=7.0622,
        lng=-73.0860,
    )
    repo.apply_import(
        import_run=ImportRun(
            import_run_id="seed-manizales-batch",
            source_name="test",
            input_filename="seed.json",
            input_sha256="manizales-seed",
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


def test_csv_counts_and_bbox() -> None:
    rows = read_csv_rows(CSV_PATH)
    assert len(rows) == 44
    assert len({r["id"] for r in rows}) == 44
    assert dict(Counter(r["kind"] for r in rows)) == {"CDA": 14, "CEA": 15, "CIA": 8, "CRC": 7}
    assert dict(Counter(r["validation_status"] for r in rows)) == {
        "confirmed_business": 19,
        "confirmed_address": 18,
        "approximate_not_confirmed": 7,
    }
    valid, errors = validate_rows(rows)
    assert errors == []
    assert len(valid) == 44
    for row in valid:
        assert row.lat is not None and row.lng is not None
        assert in_manizales_bbox(row.lat, row.lng)
        assert MANIZALES_BBOX.contains(row.lat, row.lng)


def test_geoportal_quality_upgrade_rows() -> None:
    import sys

    sys.path.insert(0, str(Path("scripts/places-catalog").resolve()))
    from manizales_geoportal_urls import (  # type: ignore
        GEOPORTAL_SOURCE_OBJECT_IDS,
        validate_official_query_url,
    )

    by_id = {r["id"]: r for r in read_csv_rows(CSV_PATH)}

    for sid, (lat, lng, dist) in EXACT_CONFIRMED.items():
        row = by_id[sid]
        assert float(row["lat"]) == pytest.approx(lat)
        assert float(row["lng"]) == pytest.approx(lng)
        assert float(row["distance_to_runt_anchor_m"]) == pytest.approx(dist)
        assert row["validation_status"] == "confirmed_address"
        assert row["precision"] == "building"
        assert row["provider"] == "manizales_geoportal_nomenclatura_predial"
        assert row["address_consistency"] == "within_100m"
        assert "OBJECTID" in row["evidence"]
        assert "derivation_method" in row["evidence"]
        assert "negocio" in row["evidence"].lower()
        errs = validate_official_query_url(row["geocode_source_url"], GEOPORTAL_SOURCE_OBJECT_IDS[sid])
        assert errs == [], (sid, errs)

    for sid, (lat, lng, dist) in INTERPOLATED_APPROX.items():
        row = by_id[sid]
        assert float(row["lat"]) == pytest.approx(lat)
        assert float(row["lng"]) == pytest.approx(lng)
        assert float(row["distance_to_runt_anchor_m"]) == pytest.approx(dist)
        assert row["validation_status"] == "approximate_not_confirmed"
        assert row["precision"] == "address_interpolation"
        assert row["provider"] == "manizales_geoportal_nomenclatura_predial_interpolation"
        errs = validate_official_query_url(row["geocode_source_url"], GEOPORTAL_SOURCE_OBJECT_IDS[sid])
        assert errs == [], (sid, errs)

    practicar = by_id["cea-manizales-cea-practicar-del-eje-manizales-71a9a35cf0"]
    assert float(practicar["lng"]) < -75.48
    assert practicar["address_consistency"] == "official_correction_over_250m"
    assert "Cerro de Oro" in practicar["evidence"]
    assert "105038" in practicar["evidence"] and "105040" in practicar["evidence"]
    assert "(59-55)/(75-55)=0.20" in practicar["evidence"]

    eje = by_id["cia-manizales-centro-integral-de-atencion-eje-cafetero-3000df8047"]
    assert "27319" in eje["evidence"] and "27346" in eje["evidence"]
    assert "(40-35)/(51-35)=0.3125" in eje["evidence"]

    for sid, (lat, lng) in UNCHANGED_APPROX.items():
        row = by_id[sid]
        assert float(row["lat"]) == pytest.approx(lat)
        assert float(row["lng"]) == pytest.approx(lng)
        assert row["validation_status"] == "approximate_not_confirmed"
        assert row["provider"] != "manizales_geoportal_nomenclatura_predial"
        assert row["provider"] != "manizales_geoportal_nomenclatura_predial_interpolation"


def test_no_control_characters_in_manizales_artifacts() -> None:
    roots = [
        Path("services/places-service/data/geocodes/manizales"),
        Path("services/places-service/data/reports/validation"),
        Path("services/places-service/data/reports/manizales_geocode_import_report.json"),
    ]
    allowed = {"\t", "\n", "\r"}
    bad: list[str] = []
    files: list[Path] = []
    for root in roots:
        if root.is_file():
            files.append(root)
        elif root.is_dir():
            files.extend(p for p in root.rglob("*") if p.is_file())
    for path in files:
        if path.suffix.lower() not in {".md", ".json", ".csv", ".txt"}:
            continue
        text = path.read_text(encoding="utf-8")
        for i, ch in enumerate(text):
            if ord(ch) < 32 and ch not in allowed:
                bad.append(f"{path}:{i}:U+{ord(ch):04X}")
                break
    assert bad == []


def test_address_normalizer_colombian_vias() -> None:
    assert "CALLE" in normalize_colombia_address("CL 12 # 30-32")
    assert "CALLE" in normalize_colombia_address("CLL 37 N 25 - 36")
    assert "CARRERA" in normalize_colombia_address("CR 23 15-47")
    assert "CARRERA" in normalize_colombia_address("CRA 26 VIA AL MAGDALENA")
    assert "CARRERA" in normalize_colombia_address("KR 19 22 40")
    assert "AVENIDA" in normalize_colombia_address("AV KEVIN ANGEL")
    assert "DIAGONAL" in normalize_colombia_address("DG 15 20")
    assert "TRANSVERSAL" in normalize_colombia_address("TV 8 10")
    assert accepts_centroid_as_business(5.0689, -75.5174) is False
    assert score_name("CDA SOCICAR", "CDA Socicar") == 1.0


def test_manizales_import_apply_idempotent_and_isolated(tmp_path: Path) -> None:
    db = tmp_path / "mz.sqlite"
    db_url = f"sqlite+pysqlite:///{db.as_posix()}"
    _seed_manizales_catalog(db_url)
    report_path = tmp_path / "report1.json"

    rc = import_manizales_geocodes.main(
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
    report = __import__("json").loads(report_path.read_text(encoding="utf-8"))
    assert report["atomic_aborted"] is False
    assert report["by_kind"] == {"CDA": 14, "CEA": 15, "CIA": 8, "CRC": 7}
    assert report["by_validation_status"]["approximate_not_confirmed"] == 7
    assert report["by_validation_status"]["confirmed_address"] == 18
    assert report["by_validation_status"]["confirmed_business"] == 19
    assert report["inserted"] + report["updated"] == 44

    repo = CatalogSqlRepository(db_url, create_schema=False)
    with repo.engine.begin() as conn:
        mz = conn.execute(
            select(places_sites).where(places_sites.c.municipality == "Manizales")
        ).mappings().all()
        assert len(mz) == 44
        assert all(r["lat"] is not None and r["lng"] is not None for r in mz)
        assert all(in_manizales_bbox(float(r["lat"]), float(r["lng"])) for r in mz)
        approx = [r for r in mz if r["geocode_validation_status"] == "approximate_not_confirmed"]
        assert len(approx) == 7
        bga = conn.execute(
            select(places_sites).where(places_sites.c.site_id.in_(("site-bga-01", "site-bga-02")))
        ).mappings().all()
        assert len(bga) == 2
        assert float(bga[0]["lat"] if bga[0]["site_id"] == "site-bga-01" else bga[1]["lat"]) in {
            7.1193,
            7.0622,
        }
        by_id = {r["site_id"]: r for r in bga}
        assert float(by_id["site-bga-01"]["lat"]) == pytest.approx(7.1193)
        assert float(by_id["site-bga-01"]["lng"]) == pytest.approx(-73.1227)
        assert by_id["site-bga-01"]["geocode_validation_status"] is None

    report2 = tmp_path / "report2.json"
    rc2 = import_manizales_geocodes.main(
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
    second = __import__("json").loads(report2.read_text(encoding="utf-8"))
    assert second["inserted"] == 0
    assert second["updated"] == 0
    assert second["unchanged"] == 44
    assert second["atomic_aborted"] is False

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
    place = _site_to_place_result(dict(row))
    assert place["validation_status"] == "approximate_not_confirmed"
    assert place["location_confirmed"] is False
    assert place["lat"] is not None
    assert place["precision"] == place["location_precision"]

    features = repo.list_geojson_features(city="Manizales", department="Caldas")
    assert len(features) == 44
    approx_feats = [
        f for f in features if f["properties"]["validation_status"] == "approximate_not_confirmed"
    ]
    assert len(approx_feats) == 7
    assert all(f["properties"]["location_confirmed"] is False for f in approx_feats)
    unconfirmed = [f for f in features if f["properties"]["location_confirmed"] is False]
    assert len(unconfirmed) == 7


def test_manizales_import_rejects_foreign_city(tmp_path: Path) -> None:
    rows = read_csv_rows(CSV_PATH)
    bad = dict(rows[0])
    bad["city"] = "Pereira"
    path = tmp_path / "bad.csv"
    with path.open("w", encoding="utf-8", newline="") as fh:
        writer = csv.DictWriter(fh, fieldnames=list(rows[0].keys()))
        writer.writeheader()
        writer.writerow(bad)
        for row in rows[1:]:
            writer.writerow(row)
    report = tmp_path / "bad_report.json"
    rc = import_manizales_geocodes.main(
        ["--input", str(path), "--dry-run", "--report-path", str(report)]
    )
    assert rc == 1
    payload = __import__("json").loads(report.read_text(encoding="utf-8"))
    assert payload["atomic_aborted"] is True
    assert payload["rejected"] >= 1


def test_manizales_dry_run_csv_only() -> None:
    rc = import_manizales_geocodes.main(
        [
            "--input",
            str(CSV_PATH),
            "--dry-run",
            "--report-path",
            "services/places-service/data/reports/manizales_geocode_import_report.json",
        ]
    )
    assert rc == 0
