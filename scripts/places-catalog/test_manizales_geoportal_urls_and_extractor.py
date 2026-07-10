"""Offline tests for Manizales geoportal URL helpers and extractor refresh."""
from __future__ import annotations

import json
import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[2]
SCRIPT_DIR = ROOT / "scripts" / "places-catalog"
sys.path.insert(0, str(SCRIPT_DIR))

from manizales_geoportal_urls import (  # noqa: E402
    DIR_FIELD,
    GEOPORTAL_SOURCE_OBJECT_IDS,
    OID_FIELD,
    ORIGINAL_AUDIT_IDS,
    build_objectids_query_url,
    validate_official_query_url,
)
import extract_manizales_nomenclatura as extract  # noqa: E402


def test_official_urls_use_objectids_and_full_field_names():
    for sid, oids in GEOPORTAL_SOURCE_OBJECT_IDS.items():
        url = build_objectids_query_url(oids)
        errs = validate_official_query_url(url, oids)
        assert errs == [], (sid, errs, url)
        assert "objectIds=" in url
        assert OID_FIELD in url or OID_FIELD.replace(".", "%2E") in url or "Construcciones_Urbanas_MASORA_NEW.OBJECTID" in url
        # urlencode keeps dots; ensure full names present after decode
        from urllib.parse import unquote

        decoded = unquote(url)
        assert OID_FIELD in decoded
        assert DIR_FIELD in decoded
        assert "outFields=*" not in url
        assert "where=direccion" not in url
        assert "outFields=OBJECTID,direccion" not in url


def test_reject_alias_urls():
    bad = (
        "https://sig.manizales.gov.co/wadmzl/rest/services/20_WEB/"
        "2020_consulta_POT_urbano_web_v10_2/MapServer/10/query?"
        "f=json&outFields=OBJECTID,direccion&where=direccion%3D%27C+12+30+32%27"
    )
    errs = validate_official_query_url(bad, (32634,))
    assert "missing_objectIds" in errs or "alias_outFields_rejected" in errs


def test_extractor_offline_refresh_with_current_csv(tmp_path: Path, monkeypatch: pytest.MonkeyPatch):
    # Point extractor outputs to temp copies so we don't clobber during unit test.
    src_json = Path("services/places-service/data/geocodes/manizales/approximate_review_inventory.json")
    tmp_json = tmp_path / "inventory.json"
    tmp_md = tmp_path / "inventory.md"
    tmp_probe = tmp_path / "probe.json"
    if src_json.exists():
        tmp_json.write_text(src_json.read_text(encoding="utf-8"), encoding="utf-8")
    monkeypatch.setattr(extract, "OUT_JSON", tmp_json)
    monkeypatch.setattr(extract, "OUT_MD", tmp_md)
    monkeypatch.setattr(extract, "OUT_PROBE", tmp_probe)

    payload = extract.offline_refresh_inventory()
    assert payload["mode"] == "offline_refresh"
    assert payload["canonical_csv_modified"] is True
    assert "no modificado" not in json.dumps(payload, ensure_ascii=False).lower()
    assert payload["scope_counts"]["total"] == 44
    assert payload["scope_counts"]["by_validation_status"] == {
        "confirmed_business": 19,
        "confirmed_address": 18,
        "approximate_not_confirmed": 7,
    }
    assert payload["original_audit_id_count"] == 12
    assert [r["id"] for r in payload["rows"]] == list(ORIGINAL_AUDIT_IDS)
    # Confirmed rows are included even though no longer approximate.
    statuses = {r["id"]: r["csv_validation_status"] for r in payload["rows"]}
    assert statuses["cda-manizales-cda-caldas-el-bosque-a730920403"] == "confirmed_address"
    assert statuses["cda-manizales-cda-socicar-7acac31f0f"] == "approximate_not_confirmed"
    assert tmp_md.exists() and "12 IDs" in tmp_md.read_text(encoding="utf-8")


def test_extractor_cli_offline(monkeypatch: pytest.MonkeyPatch, tmp_path: Path):
    src_json = Path("services/places-service/data/geocodes/manizales/approximate_review_inventory.json")
    tmp_json = tmp_path / "inventory.json"
    if src_json.exists():
        tmp_json.write_text(src_json.read_text(encoding="utf-8"), encoding="utf-8")
    monkeypatch.setattr(extract, "OUT_JSON", tmp_json)
    monkeypatch.setattr(extract, "OUT_MD", tmp_path / "inventory.md")
    monkeypatch.setattr(extract, "OUT_PROBE", tmp_path / "probe.json")
    assert extract.main(["--offline"]) == 0
