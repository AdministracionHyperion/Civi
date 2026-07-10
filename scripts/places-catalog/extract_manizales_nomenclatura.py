"""Extract official Manizales NOMENCLATURA PREDIAL geometries for approximate audit.

Privacy: only OBJECTID, direccion, representative point (area centroid or
point-on-surface), query URL, date, distances and interpolation formula.
No owners, documents, avaluos, fichas, NPN. outFields limited to OBJECTID+direccion.
"""
from __future__ import annotations

import csv
import json
import sys
import urllib.parse
import urllib.request
from datetime import datetime, timezone
from pathlib import Path

SCRIPT_DIR = Path(__file__).resolve().parent
sys.path.insert(0, str(SCRIPT_DIR))

from manizales_nomenclatura_geometry import (  # noqa: E402
    haversine_m,
    interpolate_representative_points,
    point_in_polygon,
    representative_point,
)

CSV_PATH = Path(
    "services/places-service/data/geocodes/manizales/geocodes_manizales_validado.csv"
)
OUT_JSON = Path(
    "services/places-service/data/geocodes/manizales/approximate_review_inventory.json"
)
OUT_MD = Path(
    "services/places-service/data/geocodes/manizales/approximate_review_inventory.md"
)
OUT_PROBE = Path(
    "services/places-service/data/geocodes/manizales/geoportal_nomenclatura_extract.json"
)

SERVICE = (
    "https://sig.manizales.gov.co/wadmzl/rest/services/20_WEB/"
    "2020_consulta_POT_urbano_web_v10_2/MapServer/10"
)
QUERY = SERVICE + "/query"
DIR_FIELD = "CATASTRO_13SEP2021.DBO.BDD_PREDIO_AVALUO_PROP_NEW.direccion"
OID_FIELD = "CATASTRO_13SEP2021.DBO.Construcciones_Urbanas_MASORA_NEW.OBJECTID"
# Explicit allow-list only — never outFields=*
OUT_FIELDS = ",".join([OID_FIELD, DIR_FIELD])

CONSULTED_AT = datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")

ALLOWED_STATUS = frozenset({"confirmed_address", "approximate_not_confirmed"})
ALLOWED_PRECISION = frozenset(
    {"building", "address", "address_interpolation", "nearby_address_landmark"}
)

SECONDARY = {
    "cda-manizales-cda-caldas-el-bosque-a730920403": (5.0619350, -75.5238599),
    "cda-manizales-centro-de-diagnostico-automotor-motolina-0ce021ad5c": (
        5.0667890,
        -75.5108139,
    ),
    "cea-manizales-academia-automovilistica-piloto-177f760536": (5.0682222, -75.5217211),
    "cea-manizales-cea-practicar-del-eje-manizales-71a9a35cf0": (5.0517, -75.4844),
    "cea-manizales-centro-de-ensenanza-automovilistica-cald-3e6c3b1930": (
        5.0628630,
        -75.4961049,
    ),
    "cia-manizales-centro-integral-de-atencion-rutas-de-col-e89cbc963e": (
        5.0694020,
        -75.5182809,
    ),
    "cia-manizales-centro-integral-de-atencion-eje-cafetero-3000df8047": (
        5.0689636,
        -75.5181746,
    ),
    "crc-manizales-centro-de-reconocimiento-de-conductores--dfb8fe156d": (
        5.0700560,
        -75.5177019,
    ),
}

# Vertex-mean points from commit b78dcd6 (pre shoelace fix), for displacement reporting.
VERTEX_MEAN_BASELINE = {
    "cda-manizales-cda-caldas-el-bosque-a730920403": (5.0619511, -75.5239771),
    "cda-manizales-cda-socicar-7acac31f0f": (5.069587, -75.5231293),
    "cda-manizales-centro-de-diagnostico-automotor-motolina-0ce021ad5c": (
        5.0668589,
        -75.5108467,
    ),
    "cea-manizales-academia-automovilistica-caldas-sas-12d613c393": (
        5.0626837,
        -75.4949458,
    ),
    "cea-manizales-academia-automovilistica-piloto-177f760536": (5.0680482, -75.5217908),
    "cea-manizales-cea-practicar-del-eje-manizales-71a9a35cf0": (5.0518408, -75.4841049),
    "cea-manizales-centro-de-ensenanza-automovilistica-cald-3e6c3b1930": (
        5.062791,
        -75.4962457,
    ),
    "cia-manizales-centro-integral-de-atencion-rutas-de-col-e89cbc963e": (
        5.0693862,
        -75.5180932,
    ),
    "cia-manizales-centro-integral-de-atencion-eje-cafetero-3000df8047": (
        5.0692599,
        -75.5179778,
    ),
    "crc-manizales-centro-de-reconocimiento-de-conductores--dfb8fe156d": (
        5.0700727,
        -75.5176819,
    ),
    "crc-manizales-certificamos-agustinos-98839ab670": (5.0700344, -75.5198595),
}


def query(**params) -> tuple[dict, str]:
    q = {
        "f": "json",
        "outFields": OUT_FIELDS,
        "returnGeometry": "true",
        "outSR": "4326",
        **params,
    }
    assert "*" not in str(q["outFields"])
    url = QUERY + "?" + urllib.parse.urlencode(q)
    req = urllib.request.Request(url, headers={"User-Agent": "CiviAudit/1.0"})
    with urllib.request.urlopen(req, timeout=90) as resp:
        return json.loads(resp.read().decode("utf-8")), url


def sanitize_feature(
    objectid: int,
    direccion: str,
    rep: dict,
    query_url: str,
    *,
    geom: dict | None = None,
) -> dict:
    lat = None if rep["lat"] is None else round(rep["lat"], 7)
    lng = None if rep["lng"] is None else round(rep["lng"], 7)
    out = {
        "objectid": objectid,
        "direccion": direccion,
        "representative_lat": lat,
        "representative_lng": lng,
        "derivation_method": rep.get("derivation_method"),
        "inside_polygon": rep.get("inside_polygon"),
        "needs_review": rep.get("needs_review"),
        "geometry_min": {
            "type": rep.get("derivation_method") or "unknown",
            "lat": lat,
            "lng": lng,
        },
        "query_url": query_url,
        "consulted_at": CONSULTED_AT,
    }
    if geom is not None:
        out["_geom"] = geom  # stripped before persistence
    return out


def feature_from_raw(feat: dict, query_url: str) -> dict | None:
    attrs = feat.get("attributes") or {}
    geom = feat.get("geometry") or {}
    rep = representative_point(geom)
    if rep["lat"] is None:
        return None
    oid = attrs.get(OID_FIELD)
    direccion = attrs.get(DIR_FIELD)
    if oid is None or not direccion:
        return None
    return sanitize_feature(int(oid), str(direccion), rep, query_url, geom=geom)


def strip_private(rec: dict) -> dict:
    return {k: v for k, v in rec.items() if not k.startswith("_")}


def fetch_oids(oids: list[int]) -> tuple[dict[int, dict], str]:
    where = f"{OID_FIELD} IN ({','.join(str(i) for i in oids)})"
    data, url = query(where=where)
    out: dict[int, dict] = {}
    for f in data.get("features") or []:
        rec = feature_from_raw(f, url)
        if rec:
            out[rec["objectid"]] = rec
    return out, url


def fetch_exact(address: str) -> tuple[list[dict], str]:
    where = f"{DIR_FIELD} = '{address}'"
    data, url = query(where=where)
    out = []
    seen = set()
    for f in data.get("features") or []:
        rec = feature_from_raw(f, url)
        if not rec:
            continue
        key = (rec["objectid"], rec["direccion"])
        if key in seen:
            continue
        seen.add(key)
        out.append(rec)
    return out, url


def fetch_like(pattern: str, limit: int = 100) -> tuple[list[dict], str]:
    where = f"{DIR_FIELD} LIKE '{pattern}'"
    data, url = query(where=where, resultRecordCount=str(limit))
    out = []
    seen = set()
    for f in data.get("features") or []:
        rec = feature_from_raw(f, url)
        if not rec:
            continue
        key = (rec["objectid"], rec["direccion"])
        if key in seen:
            continue
        seen.add(key)
        out.append(rec)
    return out, url


def mean_point(feats: list[dict]) -> tuple[float, float]:
    lat = sum(f["representative_lat"] for f in feats) / len(feats)
    lng = sum(f["representative_lng"] for f in feats) / len(feats)
    return round(lat, 7), round(lng, 7)


def distances(cur_lat: float, cur_lng: float, lat: float | None, lng: float | None, sec):
    d_cur = None if lat is None else round(haversine_m(cur_lat, cur_lng, lat, lng), 1)
    d_sec = None
    if lat is not None and sec:
        d_sec = round(haversine_m(sec[0], sec[1], lat, lng), 1)
    return d_cur, d_sec


def load_previous_coords() -> dict[str, dict]:
    """Prefer the frozen vertex-mean baseline (b78dcd6) for displacement reporting."""
    out = {
        sid: {
            "lat": lat,
            "lng": lng,
            "note": "vertex_mean_from_commit_b78dcd6",
        }
        for sid, (lat, lng) in VERTEX_MEAN_BASELINE.items()
    }
    return out


def propose(status: str, precision: str) -> dict:
    assert status in ALLOWED_STATUS
    assert precision in ALLOWED_PRECISION
    return {
        "csv_proposed_validation_status": status,
        "csv_proposed_precision": precision,
    }


def persistable_detail(g: dict) -> dict:
    skip = {"all_features", "records", "near_sector_top", "sample_relevant_addresses"}
    out = {}
    for k, v in g.items():
        if k in skip:
            continue
        if k == "features_used":
            out[k] = [strip_private(f) for f in (v or [])]
        elif k == "feature" and isinstance(v, dict):
            out[k] = strip_private(v)
        elif k == "interpolation" and isinstance(v, dict):
            inter = dict(v)
            if "before" in inter:
                inter["before"] = strip_private(inter["before"])
            if "after" in inter:
                inter["after"] = strip_private(inter["after"])
            out[k] = inter
        else:
            out[k] = v
    return out


def main() -> None:
    previous = load_previous_coords()
    approx = [
        r
        for r in csv.DictReader(CSV_PATH.open(encoding="utf-8-sig", newline=""))
        if r["validation_status"] == "approximate_not_confirmed"
    ]
    all_rows = list(csv.DictReader(CSV_PATH.open(encoding="utf-8-sig", newline="")))
    by_status = {}
    for r in all_rows:
        by_status[r["validation_status"]] = by_status.get(r["validation_status"], 0) + 1

    by_id = {r["id"]: r for r in approx}
    assert len(by_id) == len(approx)
    if len(approx) == 0:
        raise SystemExit("no approximate rows to audit")

    probe: dict = {
        "service": SERVICE,
        "layer": "NOMENCLATURA PREDIAL",
        "consulted_at": CONSULTED_AT,
        "outFields": OUT_FIELDS,
        "outFields_star_forbidden": True,
        "privacy_note": (
            "Solo OBJECTID, direccion, geometria minima (punto representativo), "
            "coordenada representativa, derivation_method, consulta, fecha, "
            "distancias y formula. Sin propietarios, documentos, avaluos, fichas, "
            "NPN ni consultas con outFields comodín."
        ),
        "geometry_method_note": (
            "Punto representativo = centroide de area (shoelace con traslacion al "
            "primer vertice). Si cae fuera (concavo), point_on_surface determinista."
        ),
        "queries": {},
    }
    geoportal_by_id: dict[str, dict] = {}

    # --- Exact matches ---
    exact_specs = [
        (
            "cda-manizales-cda-caldas-el-bosque-a730920403",
            ["C 12 30 32"],
            "C 12 30 32",
        ),
        (
            "cda-manizales-centro-de-diagnostico-automotor-motolina-0ce021ad5c",
            ["CR 24 32 49", "K 24 32 49"],
            "CR 24 32 49",
        ),
        (
            "cea-manizales-centro-de-ensenanza-automovilistica-cald-3e6c3b1930",
            ["K 24 53 20", "K 24 53 20 K 25", "CR 24 53 20"],
            "K 24 53 20",
        ),
        (
            "cia-manizales-centro-integral-de-atencion-rutas-de-col-e89cbc963e",
            ["C 21 19 27"],
            "C 21 19 27",
        ),
    ]
    for sid, variants, primary in exact_specs:
        chosen = None
        urls = []
        for v in variants:
            hits, url = fetch_exact(v)
            urls.append(url)
            if hits and chosen is None:
                for h in hits:
                    if (h["direccion"] or "").strip().upper().startswith(primary.upper()):
                        chosen = h
                        break
                if chosen is None:
                    chosen = hits[0]
        cur = by_id[sid]
        cur_lat, cur_lng = float(cur["lat"]), float(cur["lng"])
        sec = SECONDARY.get(sid)
        lat = None if not chosen else chosen["representative_lat"]
        lng = None if not chosen else chosen["representative_lng"]
        d_cur, d_sec = distances(cur_lat, cur_lng, lat, lng, sec)
        inside = None
        if chosen and chosen.get("_geom"):
            inside = point_in_polygon(lat, lng, chosen["_geom"])
            chosen["inside_polygon"] = inside
        prop = propose("confirmed_address", "building") if chosen and inside else propose(
            "approximate_not_confirmed", "nearby_address_landmark"
        )
        g = {
            "match_type": "exact" if chosen else "insufficient",
            "requested_address": primary,
            "variants_tried": variants,
            "feature": strip_private(chosen) if chosen else None,
            "features_used": [strip_private(chosen)] if chosen else [],
            "inside_official_polygon": inside,
            "derivation_method": None if not chosen else chosen.get("derivation_method"),
            "query_urls": urls,
            "distance_to_current_m": d_cur,
            "distance_to_secondary_m": d_sec,
            "recommended_lat": lat,
            "recommended_lng": lng,
            **prop,
            "reason": (
                "Predio oficial exacto; punto representativo verificado dentro del polígono."
                if chosen and inside
                else (
                    "Predio exacto hallado pero punto representativo fuera/revisión."
                    if chosen
                    else "No se encontró feature exacto."
                )
            ),
        }
        geoportal_by_id[sid] = g
        probe["queries"][sid] = persistable_detail(g)

    # --- Academia Piloto ---
    piloto_id = "cea-manizales-academia-automovilistica-piloto-177f760536"
    oids_piloto, url_piloto = fetch_oids([80394, 80393])
    hits38, url38 = fetch_exact("K 21 15 38")
    hits44, url44 = fetch_like("K 21 15 44%", 20)
    before_p = next((h for h in hits38 if h["objectid"] == 80394), oids_piloto[80394])
    after_p = next((h for h in hits44 if h["objectid"] == 80393), oids_piloto[80393])
    inter_p = interpolate_representative_points(
        strip_private(before_p),
        strip_private(after_p),
        target_plate=40,
        before_plate=38,
        after_plate=44,
        formula="(40-38)/(44-38)=0.333333",
    )
    cur = by_id[piloto_id]
    cur_lat, cur_lng = float(cur["lat"]), float(cur["lng"])
    sec = SECONDARY[piloto_id]
    d_cur, d_sec = distances(cur_lat, cur_lng, inter_p["lat"], inter_p["lng"], sec)
    prop = propose("approximate_not_confirmed", "address_interpolation")
    g = {
        "match_type": "interpolated",
        "requested_address": "CARRERA 21 NO. 15-40",
        "via_token": "K 21 15",
        "target_plate": 40,
        "features_used": [strip_private(before_p), strip_private(after_p)],
        "interpolation": inter_p,
        "query_urls": [url_piloto, url38, url44],
        "distance_to_current_m": d_cur,
        "distance_to_secondary_m": d_sec,
        "recommended_lat": inter_p["lat"],
        "recommended_lng": inter_p["lng"],
        **prop,
        "reason": (
            "Interpolación entre puntos representativos de placas 38 y 44 sobre K 21 15; "
            f"t={inter_p['t']} en [0,1]. Sin predio exacto 15-40."
        ),
    }
    geoportal_by_id[piloto_id] = g
    probe["queries"][piloto_id] = persistable_detail(g)

    # --- CEA Practicar ---
    practicar_id = "cea-manizales-cea-practicar-del-eje-manizales-71a9a35cf0"
    oids_pr, url_pr = fetch_oids([105038, 105040])
    hits55, url55 = fetch_exact("K 23 70 55")
    hits75, url75 = fetch_like("K 23 70 75%", 20)
    before = next((h for h in hits55 if h["objectid"] == 105038), oids_pr[105038])
    after = next((h for h in hits75 if h["objectid"] == 105040), oids_pr[105040])
    inter = interpolate_representative_points(
        strip_private(before),
        strip_private(after),
        target_plate=59,
        before_plate=55,
        after_plate=75,
        formula="(59-55)/(75-55)=0.20",
    )
    verify_delta = round(haversine_m(inter["lat"], inter["lng"], 5.051845, -75.484105), 2)
    cur = by_id[practicar_id]
    cur_lat, cur_lng = float(cur["lat"]), float(cur["lng"])
    sec = SECONDARY[practicar_id]
    d_cur, d_sec = distances(cur_lat, cur_lng, inter["lat"], inter["lng"], sec)
    prop = propose("approximate_not_confirmed", "address_interpolation")
    g = {
        "match_type": "interpolated",
        "requested_address": "CRA 23 NRO 70-59 ALTA SUIZA - AVENIDA SANTANDER",
        "via_token": "K 23 70",
        "target_plate": 59,
        "discarded_objectids": [
            {"objectid": 96475, "direccion": "K 23 70B 57", "reason": "no_encierran_correctamente_K_23_70_59"},
            {"objectid": 52515, "direccion": "K 23 70A 60", "reason": "no_encierran_correctamente_K_23_70_59"},
        ],
        "features_used": [strip_private(before), strip_private(after)],
        "interpolation": inter,
        "verification_expected": {"lat": 5.051845, "lng": -75.484105},
        "verification_delta_m": verify_delta,
        "query_urls": [url_pr, url55, url75],
        "distance_to_current_m": d_cur,
        "distance_to_secondary_m": d_sec,
        "recommended_lat": inter["lat"],
        "recommended_lng": inter["lng"],
        **prop,
        "reason": (
            "Interpolación OBJECTID 105038→105040; t=0.20. Mantener approximate_not_confirmed "
            "salvo predio exacto. Descartados 96475/52515."
        ),
    }
    geoportal_by_id[practicar_id] = g
    probe["queries"][practicar_id] = persistable_detail(g)

    # --- CIA Eje Cafetero ---
    eje_id = "cia-manizales-centro-integral-de-atencion-eje-cafetero-3000df8047"
    oids_e, url_e = fetch_oids([27319, 27346])
    hits35, url35 = fetch_like("K 20 21 35%", 20)
    hits51, url51 = fetch_exact("K 20 21 51")
    before_e = next((h for h in hits35 if h["objectid"] == 27319), oids_e[27319])
    after_e = next((h for h in hits51 if h["objectid"] == 27346), oids_e[27346])
    inter_e = interpolate_representative_points(
        strip_private(before_e),
        strip_private(after_e),
        target_plate=40,
        before_plate=35,
        after_plate=51,
        formula="(40-35)/(51-35)=0.3125",
    )
    verify_e = round(haversine_m(inter_e["lat"], inter_e["lng"], 5.069223, -75.517980), 2)
    cur = by_id[eje_id]
    cur_lat, cur_lng = float(cur["lat"]), float(cur["lng"])
    sec = SECONDARY[eje_id]
    d_cur, d_sec = distances(cur_lat, cur_lng, inter_e["lat"], inter_e["lng"], sec)
    prop = propose("approximate_not_confirmed", "address_interpolation")
    g = {
        "match_type": "interpolated",
        "requested_address": "CARRERA 20 NO.21-40",
        "via_token": "K 20 21",
        "target_plate": 40,
        "features_used": [strip_private(before_e), strip_private(after_e)],
        "interpolation": inter_e,
        "verification_expected": {"lat": 5.069223, "lng": -75.517980},
        "verification_delta_m": verify_e,
        "query_urls": [url_e, url35, url51],
        "distance_to_current_m": d_cur,
        "distance_to_secondary_m": d_sec,
        "recommended_lat": inter_e["lat"],
        "recommended_lng": inter_e["lng"],
        **prop,
        "reason": (
            "Interpolación OBJECTID 27319 (K 20 21 35) → 27346 (K 20 21 51); t=0.3125."
        ),
    }
    geoportal_by_id[eje_id] = g
    probe["queries"][eje_id] = persistable_detail(g)

    # --- Socicar: corridor evidence must be reproducible ---
    socicar_id = "cda-manizales-cda-socicar-7acac31f0f"
    oids_s, url_s = fetch_oids([80316, 80293])
    hits41, url41 = fetch_exact("K 19 13 41")
    hits45, url45 = fetch_exact("K 19 13 45 47")
    before_s = next((h for h in hits41 if h["objectid"] == 80316), oids_s[80316])
    after_s = next((h for h in hits45 if h["objectid"] == 80293), oids_s[80293])
    inter_s = interpolate_representative_points(
        strip_private(before_s),
        strip_private(after_s),
        target_plate=44,
        before_plate=41,
        after_plate=45,
        formula="(44-41)/(45-41)=0.75",
    )
    verify_s = round(haversine_m(inter_s["lat"], inter_s["lng"], 5.069589, -75.523131), 2)
    cur = by_id[socicar_id]
    cur_lat, cur_lng = float(cur["lat"]), float(cur["lng"])
    d_cur, d_sec = distances(cur_lat, cur_lng, inter_s["lat"], inter_s["lng"], None)
    corridor = {
        "runt": "AVENIDA 19",
        "municipal_candidates_queried": ["K 19 13 41", "K 19 13 45 47"],
        "objectids": [80316, 80293],
        "spatial_proximity_to_current_csv_m": d_cur,
        "confirmed": False,
        "evidence_status": "insufficient_official_alias",
        "corroboration": [
            "Se consultó NOMENCLATURA PREDIAL por dirección exacta K 19 13 41 (OBJECTID 80316) y K 19 13 45 47 (OBJECTID 80293).",
            "Ambos predios existen sobre el corredor municipal tipificado como K 19 (Carrera 19) entre calles 13.",
            "La dirección RUNT usa 'AVENIDA 19 N 13-44'; en Manizales es frecuente el alias avenida/carrera, pero esta auditoría no halló un documento oficial municipal (nomenclatura/POT/alias) que declare Avenida 19 ≡ K 19.",
            "Por tanto corridor_equivalence.confirmed=false; la interpolación se conserva solo como geometría de auditoría.",
        ],
        "reproducible_queries": [url41, url45, url_s],
    }
    prop = propose("approximate_not_confirmed", "address_interpolation")
    g = {
        "match_type": "interpolated_audit_only",
        "requested_address": "AVENIDA 19 N 13 - 44 LOCAL 3-4-5-6 AMERICAS",
        "corridor_equivalence": corridor,
        "via_token": "K 19 13",
        "target_plate": 44,
        "features_used": [strip_private(before_s), strip_private(after_s)],
        "interpolation": inter_s,
        "verification_expected": {"lat": 5.069589, "lng": -75.523131},
        "verification_delta_m": verify_s,
        "query_urls": [url_s, url41, url45],
        "distance_to_current_m": d_cur,
        "distance_to_secondary_m": d_sec,
        "recommended_lat": inter_s["lat"],
        "recommended_lng": inter_s["lng"],
        **prop,
        "reason": (
            "Interpolación K 19 13 41→45 47 hacia placa 44 documentada, pero sin evidencia "
            "oficial reproducible de que Avenida 19 RUNT ≡ K 19; proposed=approximate_not_confirmed."
        ),
    }
    geoportal_by_id[socicar_id] = g
    probe["queries"][socicar_id] = persistable_detail(g)

    # --- Academia Caldas SAS ---
    caldas_id = "cea-manizales-academia-automovilistica-caldas-sas-12d613c393"
    hits_c, url_c = fetch_exact("K 23 53A 25 27")
    oids_c, url_co = fetch_oids([26301])
    feat_c = next((h for h in hits_c if h["objectid"] == 26301), oids_c[26301])
    inside_c = None
    if feat_c.get("_geom"):
        inside_c = point_in_polygon(
            feat_c["representative_lat"], feat_c["representative_lng"], feat_c["_geom"]
        )
        feat_c["inside_polygon"] = inside_c
    verify_c = round(
        haversine_m(
            feat_c["representative_lat"],
            feat_c["representative_lng"],
            5.062709,
            -75.494958,
        ),
        2,
    )
    cur = by_id[caldas_id]
    cur_lat, cur_lng = float(cur["lat"]), float(cur["lng"])
    d_cur, d_sec = distances(
        cur_lat, cur_lng, feat_c["representative_lat"], feat_c["representative_lng"], None
    )
    prop = (
        propose("confirmed_address", "building")
        if inside_c
        else propose("approximate_not_confirmed", "address")
    )
    g = {
        "match_type": "exact_range_includes_plate",
        "requested_address_runt": "CARRERA 23 NRO 53A 25",
        "municipal_address": "K 23 53A 25 27",
        "plate_25_included_in_range": True,
        "features_used": [strip_private(feat_c)],
        "inside_official_polygon": inside_c,
        "derivation_method": feat_c.get("derivation_method"),
        "verification_expected": {"lat": 5.062709, "lng": -75.494958},
        "verification_delta_m": verify_c,
        "query_urls": [url_c, url_co],
        "distance_to_current_m": d_cur,
        "distance_to_secondary_m": d_sec,
        "recommended_lat": feat_c["representative_lat"],
        "recommended_lng": feat_c["representative_lng"],
        **prop,
        "reason": (
            "OBJECTID 26301 K 23 53A 25 27 incluye placa RUNT 25; punto representativo "
            f"derivation_method={feat_c.get('derivation_method')}, inside={inside_c}."
        ),
    }
    geoportal_by_id[caldas_id] = g
    probe["queries"][caldas_id] = persistable_detail(g)

    # --- Evaluando ---
    eval_id = "crc-manizales-centro-de-reconocimiento-de-conductores--dfb8fe156d"
    hits_ev, url_ev = fetch_exact("C 22 18 23 29")
    oids_ev, url_evo = fetch_oids([27245, 68601])
    by_oid = {}
    for h in hits_ev:
        if h["objectid"] in {27245, 68601}:
            by_oid[h["objectid"]] = h
    for oid in (27245, 68601):
        if oid not in by_oid and oid in oids_ev:
            by_oid[oid] = oids_ev[oid]
    feats_ev = [by_oid[27245], by_oid[68601]]
    insides = []
    for f in feats_ev:
        if f.get("_geom"):
            ok = point_in_polygon(f["representative_lat"], f["representative_lng"], f["_geom"])
            f["inside_polygon"] = ok
            insides.append(ok)
    lat_ev, lng_ev = mean_point(feats_ev)
    cur = by_id[eval_id]
    cur_lat, cur_lng = float(cur["lat"]), float(cur["lng"])
    sec = SECONDARY[eval_id]
    d_cur, d_sec = distances(cur_lat, cur_lng, lat_ev, lng_ev, sec)
    # Address confirmed on range, but operational review pending → keep approximate
    prop = propose("approximate_not_confirmed", "address")
    g = {
        "match_type": "exact_range_includes_plate",
        "address_confirmation": {
            "municipal_address": "C 22 18 23 29",
            "runt_address": "CALLE 22 NO. 18-29 PISO 2",
            "plate_29_included_in_range": True,
            "objectids": [27245, 68601],
            "features": [strip_private(f) for f in feats_ev],
            "representative_lat": lat_ev,
            "representative_lng": lng_ev,
            "inside_official_polygon_per_feature": insides,
            "status": "address_confirmed_on_municipal_predial_range",
        },
        "operational_review": {
            "status": "operational_status_requires_review_no_coord_change",
            "note": (
                "Separado de la confirmación de dirección. Revisar vigencia operativa "
                "RUNT 2.0. Sin cambio de coordenadas/estado CSV en esta ronda."
            ),
            "runt_2_0_active_certifying_2026": "not_listed_per_external_audit",
        },
        "features_used": [strip_private(f) for f in feats_ev],
        "query_urls": [url_ev, url_evo],
        "distance_to_current_m": d_cur,
        "distance_to_secondary_m": d_sec,
        "recommended_lat": lat_ev,
        "recommended_lng": lng_ev,
        "csv_coord_change": False,
        **prop,
        "reason": (
            "Dirección: OBJECTID 27245/68601 incluyen placa 29. Operación: revisión RUNT 2.0 "
            "pendiente → proposed approximate_not_confirmed."
        ),
    }
    geoportal_by_id[eval_id] = g
    probe["queries"][eval_id] = persistable_detail(g)

    # --- Agustinos ---
    agust_id = "crc-manizales-certificamos-agustinos-98839ab670"
    hits_a, url_a = fetch_exact("K 19 18 27 L COMERCIAL 7")
    feats_a = [h for h in hits_a if h["objectid"] in {81323, 81326, 81333, 81334}]
    assert {f["objectid"] for f in feats_a} == {81323, 81326, 81333, 81334}
    insides_a = []
    for f in feats_a:
        if f.get("_geom"):
            ok = point_in_polygon(f["representative_lat"], f["representative_lng"], f["_geom"])
            f["inside_polygon"] = ok
            insides_a.append(ok)
    lat_a, lng_a = mean_point(feats_a)
    cur = by_id[agust_id]
    cur_lat, cur_lng = float(cur["lat"]), float(cur["lng"])
    d_cur, d_sec = distances(cur_lat, cur_lng, lat_a, lng_a, None)
    prop = propose("approximate_not_confirmed", "nearby_address_landmark")
    g = {
        "match_type": "building_address_confirmed_local_not_confirmed",
        "requested_address_runt": "CRA 19 18-27 LC 3/3-1",
        "municipal_building_address_found": "K 19 18 27 L COMERCIAL 7",
        "building_base_confirmed": True,
        "local_confirmed": False,
        "do_not_merge_with": "Certificamos Terminal (NIT compartido; sedes distintas)",
        "features_used": [strip_private(f) for f in feats_a],
        "inside_official_polygon_per_feature": insides_a,
        "query_urls": [url_a],
        "distance_to_current_m": d_cur,
        "distance_to_secondary_m": d_sec,
        "recommended_lat": lat_a,
        "recommended_lng": lng_a,
        **prop,
        "reason": (
            "Edificio/dirección base K 19 18 27 confirmada (OBJECTID 81323–81334); "
            "local RUNT distinto y sin fusión. proposed=approximate_not_confirmed."
        ),
    }
    geoportal_by_id[agust_id] = g
    probe["queries"][agust_id] = persistable_detail(g)

    # --- CIMYC ---
    cimyc_id = "cia-manizales-cimyc-manizales-s-a-s-498175000a"
    prop = propose("approximate_not_confirmed", "nearby_address_landmark")
    g = {
        "match_type": "insufficient",
        "features_used": [],
        "query_urls": [],
        "distance_to_current_m": None,
        "distance_to_secondary_m": None,
        "recommended_lat": None,
        "recommended_lng": None,
        **prop,
        "reason": "Sin evidencia de punto exacto en esta ronda.",
        "unchanged_this_round": True,
    }
    geoportal_by_id[cimyc_id] = g
    probe["queries"][cimyc_id] = persistable_detail(g)

    # Build inventory + comparison to previous vertex-mean coords
    out_rows = []
    table = []
    proposed_counts = {"confirmed_address": 0, "approximate_not_confirmed": 0}
    for i, r in enumerate(approx, 1):
        sid = r["id"]
        g = geoportal_by_id[sid]
        cur_lat, cur_lng = float(r["lat"]), float(r["lng"])
        sec = SECONDARY.get(sid)
        phone = (r.get("phone") or "").strip()
        nit = (r.get("nit") or "").strip()
        feats_used = [strip_private(f) for f in (g.get("features_used") or [])]
        objectids = [f.get("objectid") for f in feats_used if f]
        prev = previous.get(sid)
        new_lat, new_lng = g.get("recommended_lat"), g.get("recommended_lng")
        displacement_m = None
        if prev and new_lat is not None:
            displacement_m = round(haversine_m(prev["lat"], prev["lng"], new_lat, new_lng), 2)
        status = g["csv_proposed_validation_status"]
        precision = g["csv_proposed_precision"]
        proposed_counts[status] += 1
        item = {
            "n": i,
            "id": sid,
            "kind": r["kind"],
            "name": r["name"],
            "address_runt": r["address"],
            "nit": nit or None,
            "phone": None if phone in {"", "0"} else phone,
            "lat_current": cur_lat,
            "lng_current": cur_lng,
            "secondary_reference": None if not sec else {"lat": sec[0], "lng": sec[1]},
            "previous_audit_point": prev,
            "recalculated_point": None
            if new_lat is None
            else {"lat": new_lat, "lng": new_lng},
            "displacement_from_previous_m": displacement_m,
            "geoportal_or_interpolation": {
                "match_type": g.get("match_type"),
                "lat": new_lat,
                "lng": new_lng,
                "objectids": objectids,
                "features": feats_used,
                "interpolation": g.get("interpolation"),
                "formula": (g.get("interpolation") or {}).get("formula"),
                "derivation_method": g.get("derivation_method"),
                "inside_official_polygon": g.get("inside_official_polygon"),
                "query_urls": g.get("query_urls") or [],
                "consulted_at": CONSULTED_AT,
                "service": SERVICE,
                "detail": persistable_detail(g),
            },
            "distance_current_to_geoportal_m": g.get("distance_to_current_m"),
            "distance_secondary_to_geoportal_m": g.get("distance_to_secondary_m"),
            "csv_validation_status": "approximate_not_confirmed",
            "csv_modified": False,
            "csv_proposed_validation_status": status,
            "csv_proposed_precision": precision,
            "reason": g.get("reason"),
            "evidence_current_csv": r.get("evidence") or "",
        }
        out_rows.append(item)
        table.append(
            {
                "id": sid,
                "address_runt": r["address"],
                "previous": f"{prev['lat']},{prev['lng']}" if prev else "—",
                "recalculated": f"{new_lat},{new_lng}" if new_lat is not None else "—",
                "displacement_m": displacement_m if displacement_m is not None else "—",
                "inside_polygon": g.get("inside_official_polygon"),
                "match_type": g.get("match_type"),
                "objectids": objectids,
                "csv_proposed_validation_status": status,
                "csv_proposed_precision": precision,
                "reason": g.get("reason"),
            }
        )

    # Hypothetical counts if proposals were applied to the 12 approximate rows only.
    p_to_confirmed = proposed_counts["confirmed_address"]
    hyp = {
        "current_csv_counts": by_status,
        "proposals_on_approximate_12": proposed_counts,
        "hypothetical_after_apply_proposals_only": {
            "confirmed_address": by_status.get("confirmed_address", 0) + p_to_confirmed,
            "approximate_not_confirmed": 12 - p_to_confirmed,
            "confirmed_business": by_status.get("confirmed_business", 0),
            "note": "Hipotético; CSV canónico no modificado.",
        },
    }

    payload = {
        "city": "Manizales",
        "canonical_csv_modified": False,
        "scope_counts_unchanged": True,
        "tests_unchanged": True,
        "official_reports_unchanged": True,
        "geoportal_service": SERVICE,
        "consulted_at": CONSULTED_AT,
        "privacy_note": probe["privacy_note"],
        "geometry_method_note": probe["geometry_method_note"],
        "secondary_geocoder_not_used_as_persistent_provider": True,
        "hypothetical_counts": hyp,
        "rows": out_rows,
        "summary_table": table,
        "probe_file": str(OUT_PROBE).replace("\\", "/"),
    }
    OUT_JSON.write_text(json.dumps(payload, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    OUT_PROBE.write_text(json.dumps(probe, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")

    lines = [
        "# Inventario Manizales aproximadas — geometría oficial NOMENCLATURA PREDIAL",
        "",
        "**CSV canónico no modificado.** Punto representativo = centroide de área (shoelace) o `point_on_surface` si el centroide cae fuera.",
        "",
        f"Servicio: `{SERVICE}`",
        f"Consulta: `{CONSULTED_AT}`",
        "",
        "Privacidad: solo OBJECTID, dirección, geometría mínima, coordenada representativa, `derivation_method`, consulta, fecha, distancias y fórmula. Sin `outFields=*`.",
        "",
        "## Conteos hipotéticos (si se aplicaran propuestas)",
        "",
        "```json",
        json.dumps(hyp, ensure_ascii=False, indent=2),
        "```",
        "",
        "## Tabla final",
        "",
        "| ID | Anterior | Recalculada | Δ m | Dentro polígono | OBJECTIDs | proposed_status | proposed_precision | Motivo |",
        "|---|---|---|---:|---|---|---|---|---|",
    ]
    for t in table:
        oids = ",".join(str(x) for x in t["objectids"]) if t["objectids"] else "—"
        inside = t["inside_polygon"]
        inside_s = "—" if inside is None else str(inside)
        lines.append(
            f"| `{t['id']}` | {t['previous']} | {t['recalculated']} | {t['displacement_m']} | "
            f"{inside_s} | {oids} | `{t['csv_proposed_validation_status']}` | "
            f"`{t['csv_proposed_precision']}` | {t['reason']} |"
        )
    lines.append("")
    for row in out_rows:
        g = row["geoportal_or_interpolation"]
        lines += [
            f"## {row['n']}. {row['name']} ({row['kind']})",
            "",
            f"- **ID:** `{row['id']}`",
            f"- **Dirección RUNT:** {row['address_runt']}",
            f"- **Actual CSV:** {row['lat_current']}, {row['lng_current']}",
            f"- **Anterior auditoría:** {row['previous_audit_point']}",
            f"- **Recalculada:** {row['recalculated_point']}",
            f"- **Desplazamiento:** {row['displacement_from_previous_m']} m",
            f"- **Tipo:** `{g.get('match_type')}`",
            f"- **OBJECTIDs:** {g.get('objectids')}",
            f"- **derivation_method:** {g.get('derivation_method')}",
            f"- **inside_official_polygon:** {g.get('inside_official_polygon')}",
            f"- **Fórmula:** {g.get('formula')}",
            f"- **csv_proposed_validation_status:** `{row['csv_proposed_validation_status']}`",
            f"- **csv_proposed_precision:** `{row['csv_proposed_precision']}`",
            f"- **Motivo:** {row['reason']}",
            "",
        ]
    OUT_MD.write_text("\n".join(lines), encoding="utf-8")

    # Privacy scan
    for path in (OUT_PROBE, OUT_JSON):
        data = json.loads(path.read_text(encoding="utf-8"))
        text = json.dumps(data, ensure_ascii=False)
        assert "outFields=*" not in text
        assert "outFields%3D*" not in text
        assert '"ficha_nuev"' not in text
        assert '"propietario"' not in text
        assert '"npn"' not in text
        # Confirm allow-listed outFields only appear as OBJECTID+direccion
        if "outFields" in text:
            assert "Construcciones_Urbanas_MASORA_NEW.OBJECTID" in text
            assert "direccion" in text

    print(
        json.dumps(
            {
                "rows": len(out_rows),
                "hypothetical": hyp,
                "displacements": [
                    {
                        "id": r["id"][-32:],
                        "prev": r["previous_audit_point"],
                        "new": r["recalculated_point"],
                        "d_m": r["displacement_from_previous_m"],
                        "status": r["csv_proposed_validation_status"],
                        "precision": r["csv_proposed_precision"],
                        "inside": r["geoportal_or_interpolation"].get("inside_official_polygon"),
                    }
                    for r in out_rows
                ],
            },
            indent=2,
            ensure_ascii=False,
        )
    )


if __name__ == "__main__":
    main()
