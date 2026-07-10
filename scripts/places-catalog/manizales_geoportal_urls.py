"""Official Manizales NOMENCLATURA PREDIAL query URL helpers (no network)."""
from __future__ import annotations

import urllib.parse
from typing import Sequence

SERVICE = (
    "https://sig.manizales.gov.co/wadmzl/rest/services/20_WEB/"
    "2020_consulta_POT_urbano_web_v10_2/MapServer/10"
)
QUERY = SERVICE + "/query"
OID_FIELD = "CATASTRO_13SEP2021.DBO.Construcciones_Urbanas_MASORA_NEW.OBJECTID"
DIR_FIELD = "CATASTRO_13SEP2021.DBO.BDD_PREDIO_AVALUO_PROP_NEW.direccion"
OUT_FIELDS = f"{OID_FIELD},{DIR_FIELD}"

# Original 12 approximate audit targets (some now confirmed_address in CSV).
ORIGINAL_AUDIT_IDS: tuple[str, ...] = (
    "cda-manizales-cda-caldas-el-bosque-a730920403",
    "cda-manizales-cda-socicar-7acac31f0f",
    "cda-manizales-centro-de-diagnostico-automotor-motolina-0ce021ad5c",
    "cea-manizales-academia-automovilistica-caldas-sas-12d613c393",
    "cea-manizales-academia-automovilistica-piloto-177f760536",
    "cea-manizales-cea-practicar-del-eje-manizales-71a9a35cf0",
    "cea-manizales-centro-de-ensenanza-automovilistica-cald-3e6c3b1930",
    "cia-manizales-centro-integral-de-atencion-rutas-de-col-e89cbc963e",
    "cia-manizales-centro-integral-de-atencion-eje-cafetero-3000df8047",
    "cia-manizales-cimyc-manizales-s-a-s-498175000a",
    "crc-manizales-centro-de-reconocimiento-de-conductores--dfb8fe156d",
    "crc-manizales-certificamos-agustinos-98839ab670",
)

# Rows whose geocode_source_url must use objectIds + full field names.
GEOPORTAL_SOURCE_OBJECT_IDS: dict[str, tuple[int, ...]] = {
    "cda-manizales-cda-caldas-el-bosque-a730920403": (32634,),
    "cda-manizales-centro-de-diagnostico-automotor-motolina-0ce021ad5c": (52874,),
    "cea-manizales-centro-de-ensenanza-automovilistica-cald-3e6c3b1930": (14593,),
    "cia-manizales-centro-integral-de-atencion-rutas-de-col-e89cbc963e": (27405,),
    "cea-manizales-academia-automovilistica-caldas-sas-12d613c393": (26301,),
    "cea-manizales-academia-automovilistica-piloto-177f760536": (80394, 80393),
    "cea-manizales-cea-practicar-del-eje-manizales-71a9a35cf0": (105038, 105040),
    "cia-manizales-centro-integral-de-atencion-eje-cafetero-3000df8047": (27319, 27346),
}


def build_objectids_query_url(object_ids: Sequence[int]) -> str:
    """Build a reproducible ArcGIS query using objectIds + full outFields names."""
    if not object_ids:
        raise ValueError("object_ids required")
    ids = ",".join(str(int(i)) for i in object_ids)
    params = {
        "f": "json",
        "objectIds": ids,
        "outFields": OUT_FIELDS,
        "returnGeometry": "true",
        "outSR": "4326",
    }
    return QUERY + "?" + urllib.parse.urlencode(params)


def parse_query_url(url: str) -> dict[str, str]:
    parsed = urllib.parse.urlparse(url)
    return {k: v[0] if len(v) == 1 else ",".join(v) for k, v in urllib.parse.parse_qs(parsed.query).items()}


def validate_official_query_url(url: str, expected_object_ids: Sequence[int]) -> list[str]:
    """Offline structural validation of a geocode_source_url. Returns error reasons."""
    errors: list[str] = []
    if "outFields=*" in url or "outFields%3D*" in url.lower():
        errors.append("outFields_star_forbidden")
    if "sig.manizales.gov.co" not in url:
        errors.append("unexpected_host")
    qs = parse_query_url(url)
    if "objectIds" not in qs:
        errors.append("missing_objectIds")
    else:
        got = [int(x) for x in qs["objectIds"].split(",") if x.strip()]
        if got != list(expected_object_ids):
            errors.append(f"objectIds_mismatch:{got}!={list(expected_object_ids)}")
    out_fields = qs.get("outFields") or ""
    if OID_FIELD not in out_fields:
        errors.append("missing_full_oid_field")
    if DIR_FIELD not in out_fields:
        errors.append("missing_full_direccion_field")
    # Reject short aliases that ArcGIS rejects on this layer.
    if out_fields in {"OBJECTID,direccion", "direccion,OBJECTID"}:
        errors.append("alias_outFields_rejected")
    if "where=" in url and "objectIds=" not in url:
        errors.append("where_without_objectIds")
    return errors
