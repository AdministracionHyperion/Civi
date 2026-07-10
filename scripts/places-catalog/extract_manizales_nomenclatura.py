"""Extract official Manizales NOMENCLATURA PREDIAL geometries for approximate audit.

Privacy: only OBJECTID, direccion, representative centroid, query URL, date,
distances and interpolation formula. No owners, documents, avaluos, fichas, NPN.
"""
from __future__ import annotations

import csv
import json
import math
import urllib.parse
import urllib.request
from datetime import datetime, timezone
from pathlib import Path

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
OUT_FIELDS = ",".join([OID_FIELD, DIR_FIELD])

CONSULTED_AT = datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")

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


def haversine_m(lat1: float, lng1: float, lat2: float, lng2: float) -> float:
    r = 6371000.0
    p1, p2 = math.radians(lat1), math.radians(lat2)
    dp = math.radians(lat2 - lat1)
    dl = math.radians(lng2 - lng1)
    a = math.sin(dp / 2) ** 2 + math.cos(p1) * math.cos(p2) * math.sin(dl / 2) ** 2
    return 2 * r * math.asin(math.sqrt(a))


def query(**params) -> tuple[dict, str]:
    q = {
        "f": "json",
        "outFields": OUT_FIELDS,
        "returnGeometry": "true",
        "outSR": "4326",
        **params,
    }
    url = QUERY + "?" + urllib.parse.urlencode(q)
    req = urllib.request.Request(url, headers={"User-Agent": "CiviAudit/1.0"})
    with urllib.request.urlopen(req, timeout=90) as resp:
        return json.loads(resp.read().decode("utf-8")), url


def centroid(geom: dict) -> tuple[float, float] | None:
    rings = geom.get("rings") or []
    if not rings:
        return None
    xs = [p[0] for p in rings[0]]
    ys = [p[1] for p in rings[0]]
    return (sum(ys) / len(ys), sum(xs) / len(xs))


def sanitize_feature(objectid: int, direccion: str, lat: float, lng: float, query_url: str) -> dict:
    return {
        "objectid": objectid,
        "direccion": direccion,
        "representative_lat": round(lat, 7),
        "representative_lng": round(lng, 7),
        "geometry_min": {"type": "centroid", "lat": round(lat, 7), "lng": round(lng, 7)},
        "query_url": query_url,
        "consulted_at": CONSULTED_AT,
    }


def feature_from_raw(feat: dict, query_url: str) -> dict | None:
    attrs = feat.get("attributes") or {}
    c = centroid(feat.get("geometry") or {})
    if c is None:
        return None
    oid = attrs.get(OID_FIELD)
    direccion = attrs.get(DIR_FIELD)
    if oid is None or not direccion:
        return None
    return sanitize_feature(int(oid), str(direccion), c[0], c[1], query_url)


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


def lerp(a: float, b: float, t: float) -> float:
    return a + (b - a) * t


def interpolate_forced(
    before: dict,
    after: dict,
    *,
    target_plate: int,
    before_plate: int,
    after_plate: int,
    formula: str,
) -> dict:
    t = (target_plate - before_plate) / (after_plate - before_plate)
    lat = lerp(before["representative_lat"], after["representative_lat"], t)
    lng = lerp(before["representative_lng"], after["representative_lng"], t)
    return {
        "lat": round(lat, 7),
        "lng": round(lng, 7),
        "method": "linear_interpolation_between_predial_centroids",
        "target_plate": target_plate,
        "before_plate": before_plate,
        "after_plate": after_plate,
        "t": round(t, 6),
        "formula": formula,
        "before": before,
        "after": after,
    }


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


def main() -> None:
    approx = [
        r
        for r in csv.DictReader(CSV_PATH.open(encoding="utf-8-sig", newline=""))
        if r["validation_status"] == "approximate_not_confirmed"
    ]
    by_id = {r["id"]: r for r in approx}
    assert len(by_id) == 12

    probe: dict = {
        "service": SERVICE,
        "layer": "NOMENCLATURA PREDIAL",
        "consulted_at": CONSULTED_AT,
        "privacy_note": (
            "Solo OBJECTID, direccion, geometria minima (centroide), coordenada "
            "representativa, consulta, fecha, distancias y formula. Sin propietarios, "
            "documentos, avaluos, fichas catastrales, NPN ni otros datos personales."
        ),
        "queries": {},
    }
    geoportal_by_id: dict[str, dict] = {}

    # --- Exact matches (unchanged logic, privacy-safe) ---
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
        all_hits = []
        for v in variants:
            hits, url = fetch_exact(v)
            urls.append(url)
            all_hits.extend(hits)
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
        g = {
            "match_type": "exact" if chosen else "insufficient",
            "requested_address": primary,
            "variants_tried": variants,
            "feature": chosen,
            "features_used": [chosen] if chosen else [],
            "query_urls": urls,
            "distance_to_current_m": d_cur,
            "distance_to_secondary_m": d_sec,
            "recommended_status": (
                "candidate_for_confirmed_address_using_geoportal_geometry"
                if chosen
                else "keep_approximate_not_confirmed"
            ),
            "recommended_lat": lat,
            "recommended_lng": lng,
            "reason": (
                "Geometría centroide del predio oficial con dirección coincidente."
                if chosen
                else "No se encontró feature exacto."
            ),
        }
        geoportal_by_id[sid] = g
        probe["queries"][sid] = g

    # --- Academia Piloto: bracket 38–44 on K 21 15 ---
    piloto_id = "cea-manizales-academia-automovilistica-piloto-177f760536"
    oids_piloto, url_piloto = fetch_oids([80394, 80393])
    before_p = oids_piloto[80394]
    after_p = oids_piloto[80393]
    # Prefer address-filtered if available
    hits38, url38 = fetch_exact("K 21 15 38")
    hits44, url44 = fetch_like("K 21 15 44%", 20)
    if hits38:
        before_p = hits38[0]
    if hits44:
        after_p = next((h for h in hits44 if h["objectid"] == 80393), hits44[0])
    inter_p = interpolate_forced(
        before_p,
        after_p,
        target_plate=40,
        before_plate=38,
        after_plate=44,
        formula="(40-38)/(44-38)=0.3333",
    )
    cur = by_id[piloto_id]
    cur_lat, cur_lng = float(cur["lat"]), float(cur["lng"])
    sec = SECONDARY[piloto_id]
    d_cur, d_sec = distances(cur_lat, cur_lng, inter_p["lat"], inter_p["lng"], sec)
    g = {
        "match_type": "interpolated",
        "requested_address": "CARRERA 21 NO. 15-40",
        "via_token": "K 21 15",
        "target_plate": 40,
        "features_used": [before_p, after_p],
        "interpolation": inter_p,
        "query_urls": [url_piloto, url38, url44],
        "distance_to_current_m": d_cur,
        "distance_to_secondary_m": d_sec,
        "recommended_status": "candidate_approximate_or_address_via_municipal_interpolation",
        "recommended_lat": inter_p["lat"],
        "recommended_lng": inter_p["lng"],
        "reason": (
            "Interpolación entre placas 38 y 44 sobre K 21 15 "
            "(no existe predio exacto 15-40)."
        ),
    }
    geoportal_by_id[piloto_id] = g
    probe["queries"][piloto_id] = g

    # --- 1) CEA Practicar: forced 105038 / 105040; discard 96475 / 52515 ---
    practicar_id = "cea-manizales-cea-practicar-del-eje-manizales-71a9a35cf0"
    oids_pr, url_pr = fetch_oids([105038, 105040])
    hits55, url55 = fetch_exact("K 23 70 55")
    hits75, url75 = fetch_like("K 23 70 75%", 20)
    before = next((h for h in hits55 if h["objectid"] == 105038), oids_pr[105038])
    after = next((h for h in hits75 if h["objectid"] == 105040), oids_pr[105040])
    # Ensure address labels from address query when available
    if hits55:
        before = next(h for h in hits55 if h["objectid"] == 105038)
    if hits75:
        after = next(h for h in hits75 if h["objectid"] == 105040)
    inter = interpolate_forced(
        before,
        after,
        target_plate=59,
        before_plate=55,
        after_plate=75,
        formula="(59-55)/(75-55)=0.20",
    )
    # Verify ~5.051845, -75.484105
    verify_delta = round(haversine_m(inter["lat"], inter["lng"], 5.051845, -75.484105), 2)
    cur = by_id[practicar_id]
    cur_lat, cur_lng = float(cur["lat"]), float(cur["lng"])
    sec = SECONDARY[practicar_id]
    d_cur, d_sec = distances(cur_lat, cur_lng, inter["lat"], inter["lng"], sec)
    g = {
        "match_type": "interpolated",
        "requested_address": "CRA 23 NRO 70-59 ALTA SUIZA - AVENIDA SANTANDER",
        "via_token": "K 23 70",
        "target_plate": 59,
        "discarded_objectids": [
            {"objectid": 96475, "direccion": "K 23 70B 57", "reason": "no_encierran_correctamente_K_23_70_59"},
            {"objectid": 52515, "direccion": "K 23 70A 60", "reason": "no_encierran_correctamente_K_23_70_59"},
        ],
        "features_used": [before, after],
        "interpolation": inter,
        "verification_expected": {"lat": 5.051845, "lng": -75.484105},
        "verification_delta_m": verify_delta,
        "query_urls": [url_pr, url55, url75],
        "distance_to_current_m": d_cur,
        "distance_to_secondary_m": d_sec,
        "recommended_status": "approximate_not_confirmed_with_corrected_municipal_interpolation",
        "recommended_lat": inter["lat"],
        "recommended_lng": inter["lng"],
        "reason": (
            "Interpolación forzada OBJECTID 105038 (K 23 70 55) → 105040 (K 23 70 75); "
            "t=(59-55)/(75-55)=0.20. Descartados 96475/52515. Mantener "
            "approximate_not_confirmed salvo predio exacto."
        ),
    }
    geoportal_by_id[practicar_id] = g
    probe["queries"][practicar_id] = g

    # --- 2) CIA Eje Cafetero: 27319 / 27346 ---
    eje_id = "cia-manizales-centro-integral-de-atencion-eje-cafetero-3000df8047"
    oids_e, url_e = fetch_oids([27319, 27346])
    hits35, url35 = fetch_like("K 20 21 35%", 20)
    hits51, url51 = fetch_exact("K 20 21 51")
    before_e = next((h for h in hits35 if h["objectid"] == 27319), oids_e[27319])
    after_e = next((h for h in hits51 if h["objectid"] == 27346), oids_e[27346])
    if hits35:
        before_e = next(h for h in hits35 if h["objectid"] == 27319)
    if hits51:
        after_e = next(h for h in hits51 if h["objectid"] == 27346)
    inter_e = interpolate_forced(
        before_e,
        after_e,
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
    g = {
        "match_type": "interpolated",
        "requested_address": "CARRERA 20 NO.21-40",
        "via_token": "K 20 21",
        "target_plate": 40,
        "correction_note": "Existe posterior OBJECTID 27346 (K 20 21 51); no afirmar solo placa 35.",
        "features_used": [before_e, after_e],
        "interpolation": inter_e,
        "verification_expected": {"lat": 5.069223, "lng": -75.517980},
        "verification_delta_m": verify_e,
        "query_urls": [url_e, url35, url51],
        "distance_to_current_m": d_cur,
        "distance_to_secondary_m": d_sec,
        "recommended_status": "candidate_approximate_or_address_via_municipal_interpolation",
        "recommended_lat": inter_e["lat"],
        "recommended_lng": inter_e["lng"],
        "reason": (
            "Interpolación OBJECTID 27319 (K 20 21 35) → 27346 (K 20 21 51); "
            "t=(40-35)/(51-35)=0.3125."
        ),
    }
    geoportal_by_id[eje_id] = g
    probe["queries"][eje_id] = g

    # --- 3) Socicar: Av 19 RUNT = K 19 municipal; 80316 / 80293 → placa 44 ---
    socicar_id = "cda-manizales-cda-socicar-7acac31f0f"
    oids_s, url_s = fetch_oids([80316, 80293])
    hits41, url41 = fetch_exact("K 19 13 41")
    hits45, url45 = fetch_exact("K 19 13 45 47")
    before_s = next((h for h in hits41 if h["objectid"] == 80316), oids_s[80316])
    after_s = next((h for h in hits45 if h["objectid"] == 80293), oids_s[80293])
    if hits41:
        before_s = next(h for h in hits41 if h["objectid"] == 80316)
    if hits45:
        after_s = next(h for h in hits45 if h["objectid"] == 80293)
    inter_s = interpolate_forced(
        before_s,
        after_s,
        target_plate=44,
        before_plate=41,
        after_plate=45,
        formula="(44-41)/(45-41)=0.75",
    )
    verify_s = round(haversine_m(inter_s["lat"], inter_s["lng"], 5.069589, -75.523131), 2)
    cur = by_id[socicar_id]
    cur_lat, cur_lng = float(cur["lat"]), float(cur["lng"])
    d_cur, d_sec = distances(cur_lat, cur_lng, inter_s["lat"], inter_s["lng"], None)
    g = {
        "match_type": "interpolated",
        "requested_address": "AVENIDA 19 N 13 - 44 LOCAL 3-4-5-6 AMERICAS",
        "corridor_equivalence": {
            "runt": "AVENIDA 19",
            "municipal": "K 19",
            "confirmed": True,
            "note": "Avenida 19 del RUNT corresponde al corredor municipal K 19.",
        },
        "via_token": "K 19 13",
        "target_plate": 44,
        "features_used": [before_s, after_s],
        "interpolation": inter_s,
        "verification_expected": {"lat": 5.069589, "lng": -75.523131},
        "verification_delta_m": verify_s,
        "query_urls": [url_s, url41, url45],
        "distance_to_current_m": d_cur,
        "distance_to_secondary_m": d_sec,
        "recommended_status": "candidate_approximate_or_address_via_municipal_interpolation",
        "recommended_lat": inter_s["lat"],
        "recommended_lng": inter_s["lng"],
        "reason": (
            "Av. 19 RUNT = K 19 municipal. Interpolación OBJECTID 80316 (K 19 13 41) → "
            "80293 (K 19 13 45 47) hacia placa 44; t=(44-41)/(45-41)=0.75. Locales no confirmados."
        ),
    }
    geoportal_by_id[socicar_id] = g
    probe["queries"][socicar_id] = g

    # --- 4) Academia Caldas SAS: 26301 range includes plate 25 ---
    caldas_id = "cea-manizales-academia-automovilistica-caldas-sas-12d613c393"
    hits_c, url_c = fetch_exact("K 23 53A 25 27")
    oids_c, url_co = fetch_oids([26301])
    feat_c = next((h for h in hits_c if h["objectid"] == 26301), oids_c[26301])
    if hits_c:
        feat_c = next(h for h in hits_c if h["objectid"] == 26301)
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
    g = {
        "match_type": "exact_range_includes_plate",
        "requested_address_runt": "CARRERA 23 NRO 53A 25",
        "municipal_address": "K 23 53A 25 27",
        "plate_25_included_in_range": True,
        "features_used": [feat_c],
        "verification_expected": {"lat": 5.062709, "lng": -75.494958},
        "verification_delta_m": verify_c,
        "query_urls": [url_c, url_co],
        "distance_to_current_m": d_cur,
        "distance_to_secondary_m": d_sec,
        "recommended_status": "candidate_for_confirmed_address_using_geoportal_geometry",
        "recommended_lat": feat_c["representative_lat"],
        "recommended_lng": feat_c["representative_lng"],
        "reason": (
            "OBJECTID 26301 dirección municipal K 23 53A 25 27 incluye la placa RUNT 25; "
            "punto representativo del predio."
        ),
    }
    geoportal_by_id[caldas_id] = g
    probe["queries"][caldas_id] = g

    # --- 5) Evaluando: address confirmation vs operational review ---
    eval_id = "crc-manizales-centro-de-reconocimiento-de-conductores--dfb8fe156d"
    hits_ev, url_ev = fetch_exact("C 22 18 23 29")
    oids_ev, url_evo = fetch_oids([27245, 68601])
    feats_ev = [h for h in hits_ev if h["objectid"] in {27245, 68601}]
    if len(feats_ev) < 2:
        for oid in (27245, 68601):
            if oid in oids_ev and not any(f["objectid"] == oid for f in feats_ev):
                # Prefer address-query label when present
                feats_ev.append(oids_ev[oid])
    # Dedup and force address label from exact query
    by_oid = {}
    for h in hits_ev:
        if h["objectid"] in {27245, 68601}:
            by_oid[h["objectid"]] = h
    for oid in (27245, 68601):
        if oid not in by_oid and oid in oids_ev:
            by_oid[oid] = oids_ev[oid]
    feats_ev = [by_oid[27245], by_oid[68601]]
    lat_ev, lng_ev = mean_point(feats_ev)
    cur = by_id[eval_id]
    cur_lat, cur_lng = float(cur["lat"]), float(cur["lng"])
    sec = SECONDARY[eval_id]
    d_cur, d_sec = distances(cur_lat, cur_lng, lat_ev, lng_ev, sec)
    g = {
        "match_type": "exact_range_includes_plate",
        "address_confirmation": {
            "municipal_address": "C 22 18 23 29",
            "runt_address": "CALLE 22 NO. 18-29 PISO 2",
            "plate_29_included_in_range": True,
            "objectids": [27245, 68601],
            "features": feats_ev,
            "representative_lat": lat_ev,
            "representative_lng": lng_ev,
            "status": "address_confirmed_on_municipal_predial_range",
        },
        "operational_review": {
            "status": "operational_status_requires_review_no_coord_change",
            "note": (
                "Separado de la confirmación de dirección. RUNT directorio clásico lista "
                "Calle 22 #18-29 piso 2; revisar vigencia operativa en RUNT 2.0. "
                "Sin cambio de coordenadas/estado CSV en esta ronda."
            ),
            "runt_2_0_active_certifying_2026": "not_listed_per_external_audit",
        },
        "features_used": feats_ev,
        "query_urls": [url_ev, url_evo],
        "distance_to_current_m": d_cur,
        "distance_to_secondary_m": d_sec,
        "recommended_status": "address_confirmed_operational_review_pending_no_coord_change",
        "recommended_lat": lat_ev,
        "recommended_lng": lng_ev,
        "csv_coord_change": False,
        "reason": (
            "Dirección: OBJECTID 27245/68601 C 22 18 23 29 incluye placa 29. "
            "Operación: revisión de vigencia RUNT 2.0 pendiente; no cambiar coords/estado CSV."
        ),
    }
    geoportal_by_id[eval_id] = g
    probe["queries"][eval_id] = g

    # --- 6) Certificamos Agustinos: building only, not local ---
    agust_id = "crc-manizales-certificamos-agustinos-98839ab670"
    hits_a, url_a = fetch_exact("K 19 18 27 L COMERCIAL 7")
    feats_a = [h for h in hits_a if h["objectid"] in {81323, 81326, 81333, 81334}]
    assert {f["objectid"] for f in feats_a} == {81323, 81326, 81333, 81334}
    lat_a, lng_a = mean_point(feats_a)
    cur = by_id[agust_id]
    cur_lat, cur_lng = float(cur["lat"]), float(cur["lng"])
    d_cur, d_sec = distances(cur_lat, cur_lng, lat_a, lng_a, None)
    g = {
        "match_type": "building_address_confirmed_local_not_confirmed",
        "requested_address_runt": "CRA 19 18-27 LC 3/3-1",
        "municipal_building_address_found": "K 19 18 27 L COMERCIAL 7",
        "building_base_confirmed": True,
        "local_confirmed": False,
        "do_not_merge_with": "Certificamos Terminal (NIT compartido; sedes distintas)",
        "features_used": feats_a,
        "query_urls": [url_a],
        "distance_to_current_m": d_cur,
        "distance_to_secondary_m": d_sec,
        "recommended_status": "building_address_confirmed_local_and_merge_not_confirmed",
        "recommended_lat": lat_a,
        "recommended_lng": lng_a,
        "reason": (
            "OBJECTID 81323/81326/81333/81334 confirman edificio/dirección base "
            "K 19 18 27; RUNT usa otro local (LC 3/3-1 vs L COMERCIAL 7). "
            "No confirmar local ni fusionar establecimientos."
        ),
    }
    geoportal_by_id[agust_id] = g
    probe["queries"][agust_id] = g

    # --- CIMYC unchanged ---
    cimyc_id = "cia-manizales-cimyc-manizales-s-a-s-498175000a"
    g = {
        "match_type": "insufficient",
        "features_used": [],
        "query_urls": [],
        "distance_to_current_m": None,
        "distance_to_secondary_m": None,
        "recommended_status": "keep_approximate_insufficient_evidence",
        "recommended_lat": None,
        "recommended_lng": None,
        "reason": "Sin evidencia de punto exacto en esta ronda.",
        "unchanged_this_round": True,
    }
    geoportal_by_id[cimyc_id] = g
    probe["queries"][cimyc_id] = g

    # Build inventory
    out_rows = []
    table = []
    for i, r in enumerate(approx, 1):
        sid = r["id"]
        g = geoportal_by_id[sid]
        cur_lat, cur_lng = float(r["lat"]), float(r["lng"])
        sec = SECONDARY.get(sid)
        phone = (r.get("phone") or "").strip()
        nit = (r.get("nit") or "").strip()
        feats_used = g.get("features_used") or []
        if g.get("feature") and not feats_used:
            feats_used = [g["feature"]]
        objectids = [f.get("objectid") for f in feats_used if f]
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
            "geoportal_or_interpolation": {
                "match_type": g.get("match_type"),
                "lat": g.get("recommended_lat"),
                "lng": g.get("recommended_lng"),
                "objectids": objectids,
                "features": feats_used,
                "interpolation": g.get("interpolation"),
                "formula": (g.get("interpolation") or {}).get("formula"),
                "query_urls": g.get("query_urls") or [],
                "consulted_at": CONSULTED_AT,
                "service": SERVICE,
                "detail": {
                    k: v
                    for k, v in g.items()
                    if k
                    not in {
                        "all_features",
                        "records",
                        "near_sector_top",
                        "sample_relevant_addresses",
                    }
                },
            },
            "distance_current_to_geoportal_m": g.get("distance_to_current_m"),
            "distance_secondary_to_geoportal_m": g.get("distance_to_secondary_m"),
            "csv_validation_status": "approximate_not_confirmed",
            "csv_modified": False,
            "recommended_status": g.get("recommended_status"),
            "reason": g.get("reason"),
            "evidence_current_csv": r.get("evidence") or "",
        }
        out_rows.append(item)
        table.append(
            {
                "id": sid,
                "address_runt": r["address"],
                "lat_lng_current": f"{cur_lat},{cur_lng}",
                "lat_lng_secondary": f"{sec[0]},{sec[1]}" if sec else "—",
                "lat_lng_geoportal_or_interpolation": (
                    f"{g.get('recommended_lat')},{g.get('recommended_lng')}"
                    if g.get("recommended_lat") is not None
                    else "—"
                ),
                "match_type": g.get("match_type"),
                "objectids": objectids,
                "source": SERVICE,
                "recommended_status": g.get("recommended_status"),
                "reason": g.get("reason"),
            }
        )

    payload = {
        "city": "Manizales",
        "canonical_csv_modified": False,
        "scope_counts_unchanged": True,
        "tests_unchanged": True,
        "official_reports_unchanged": True,
        "geoportal_service": SERVICE,
        "consulted_at": CONSULTED_AT,
        "privacy_note": probe["privacy_note"],
        "secondary_geocoder_not_used_as_persistent_provider": True,
        "rows": out_rows,
        "summary_table": table,
        "probe_file": str(OUT_PROBE).replace("\\", "/"),
    }
    OUT_JSON.write_text(json.dumps(payload, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    OUT_PROBE.write_text(json.dumps(probe, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")

    lines = [
        "# Inventario Manizales aproximadas — geometría oficial NOMENCLATURA PREDIAL",
        "",
        "**CSV canónico no modificado.** Coordenadas finales propuestas salen del Geoportal (o interpolación municipal documentada), no del geocodificador secundario.",
        "",
        f"Servicio: `{SERVICE}`",
        f"Consulta: `{CONSULTED_AT}`",
        "",
        "Privacidad del extracto: solo OBJECTID, dirección, geometría mínima (centroide), coordenada representativa, consulta, fecha, distancias y fórmula.",
        "",
        "## Tabla final",
        "",
        "| ID | Dirección RUNT | Actual | Secundaria | Geoportal/interpolación | Tipo | OBJECTIDs | Estado recomendado | Motivo |",
        "|---|---|---|---|---|---|---|---|---|",
    ]
    for t in table:
        oids = ",".join(str(x) for x in t["objectids"]) if t["objectids"] else "—"
        lines.append(
            f"| `{t['id']}` | {t['address_runt']} | {t['lat_lng_current']} | "
            f"{t['lat_lng_secondary']} | {t['lat_lng_geoportal_or_interpolation']} | "
            f"`{t['match_type']}` | {oids} | `{t['recommended_status']}` | {t['reason']} |"
        )
    lines.append("")
    for row in out_rows:
        g = row["geoportal_or_interpolation"]
        formula = g.get("formula")
        lines += [
            f"## {row['n']}. {row['name']} ({row['kind']})",
            "",
            f"- **ID:** `{row['id']}`",
            f"- **Dirección RUNT:** {row['address_runt']}",
            f"- **Actual:** {row['lat_current']}, {row['lng_current']}",
            f"- **Secundaria:** {row['secondary_reference']}",
            f"- **Geoportal/interpolación:** {g.get('lat')}, {g.get('lng')}",
            f"- **Tipo:** `{g.get('match_type')}`",
            f"- **OBJECTIDs:** {g.get('objectids')}",
            f"- **Fórmula:** {formula}",
            f"- **Dist. a actual:** {row['distance_current_to_geoportal_m']} m",
            f"- **Dist. a secundaria:** {row['distance_secondary_to_geoportal_m']} m",
            f"- **Estado recomendado:** `{row['recommended_status']}`",
            f"- **Motivo:** {row['reason']}",
            f"- **URLs:** {g.get('query_urls')}",
            "",
        ]
    OUT_MD.write_text("\n".join(lines), encoding="utf-8")

    required = [105038, 105040, 27346, 80316, 80293, 26301, 27245, 68601]
    found = set()
    for t in table:
        found.update(t["objectids"])
    missing = [x for x in required if x not in found]
    print(
        json.dumps(
            {
                "rows": len(out_rows),
                "required_objectids_missing": missing,
                "verification": {
                    "practicar_delta_m": geoportal_by_id[practicar_id].get("verification_delta_m"),
                    "eje_delta_m": geoportal_by_id[eje_id].get("verification_delta_m"),
                    "socicar_delta_m": geoportal_by_id[socicar_id].get("verification_delta_m"),
                    "caldas_delta_m": geoportal_by_id[caldas_id].get("verification_delta_m"),
                },
            },
            indent=2,
        )
    )
    for t in table:
        print(t["match_type"], t["id"][-36:], t["lat_lng_geoportal_or_interpolation"], t["objectids"])


if __name__ == "__main__":
    main()
