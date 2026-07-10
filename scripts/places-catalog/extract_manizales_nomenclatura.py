"""Extract official Manizales NOMENCLATURA PREDIAL geometries for approximate audit."""
from __future__ import annotations

import csv
import json
import math
import re
import urllib.parse
import urllib.request
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
FICHA_FIELD = "CATASTRO_13SEP2021.DBO.BDD_PREDIO_AVALUO_PROP_NEW.ficha_nuev"
BARRIO_FIELD = "CATASTRO_13SEP2021.DBO.BDD_PREDIO_AVALUO_PROP_NEW.barrio"
OUT_FIELDS = ",".join([OID_FIELD, DIR_FIELD, FICHA_FIELD, BARRIO_FIELD])

# Secondary references from prior audit round (not final coords).
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


def query(**params) -> dict:
    q = {
        "f": "json",
        "outFields": OUT_FIELDS,
        "returnGeometry": "true",
        "outSR": "4326",
        **params,
    }
    url = QUERY + "?" + urllib.parse.urlencode(q)
    req = urllib.request.Request(url, headers={"User-Agent": "CiviAudit/1.0"})
    with urllib.request.urlopen(req, timeout=60) as resp:
        return json.loads(resp.read().decode("utf-8")), url


def centroid(geom: dict) -> tuple[float, float] | None:
    rings = geom.get("rings") or []
    if not rings:
        return None
    xs, ys = [], []
    for x, y in rings[0]:
        xs.append(x)
        ys.append(y)
    return (sum(ys) / len(ys), sum(xs) / len(xs))


def feature_record(feat: dict, query_url: str) -> dict:
    attrs = feat.get("attributes") or {}
    c = centroid(feat.get("geometry") or {})
    return {
        "objectid": attrs.get(OID_FIELD),
        "ficha_nuev": attrs.get(FICHA_FIELD),
        "direccion": attrs.get(DIR_FIELD),
        "barrio": attrs.get(BARRIO_FIELD),
        "lat": None if c is None else round(c[0], 7),
        "lng": None if c is None else round(c[1], 7),
        "query_url": query_url,
    }


def fetch_exact(address: str) -> tuple[list[dict], str]:
    where = f"{DIR_FIELD} = '{address}'"
    data, url = query(where=where)
    feats = data.get("features") or []
    return [feature_record(f, url) for f in feats], url


def fetch_like(pattern: str, limit: int = 100) -> tuple[list[dict], str]:
    where = f"{DIR_FIELD} LIKE '{pattern}'"
    data, url = query(where=where, resultRecordCount=str(limit))
    feats = data.get("features") or []
    # Deduplicate by objectid+direccion
    seen = set()
    out = []
    for f in feats:
        rec = feature_record(f, url)
        key = (rec["objectid"], rec["direccion"])
        if key in seen:
            continue
        seen.add(key)
        out.append(rec)
    return out, url


def parse_placa(direccion: str, via_token: str) -> int | None:
    """Extract house number after via token, e.g. 'K 21 15 38' -> 38 for via K 21 15."""
    if not direccion:
        return None
    d = direccion.upper().replace("-", " ")
    d = re.sub(r"\s+", " ", d).strip()
    # Normalize CR -> K for matching
    d_norm = d.replace("CR ", "K ").replace("CRA ", "K ").replace("CARRERA ", "K ")
    d_norm = d_norm.replace("CL ", "C ").replace("CALLE ", "C ")
    vt = via_token.upper().replace("CR ", "K ").replace("CL ", "C ")
    if not d_norm.startswith(vt + " ") and vt + " " not in d_norm[: len(vt) + 5]:
        # allow exact prefix
        if not d_norm.startswith(vt):
            return None
    # numbers after via
    rest = d_norm[len(vt) :].strip() if d_norm.startswith(vt) else None
    if rest is None:
        m = re.search(re.escape(vt) + r"\s+(.*)", d_norm)
        rest = m.group(1) if m else ""
    nums = re.findall(r"\d+", rest)
    if not nums:
        return None
    return int(nums[0])


def interpolate(
    before: dict, after: dict, target: int, before_n: int, after_n: int
) -> dict:
    if after_n == before_n:
        raise ValueError("cannot interpolate equal plate numbers")
    t = (target - before_n) / (after_n - before_n)
    lat = before["lat"] + t * (after["lat"] - before["lat"])
    lng = before["lng"] + t * (after["lng"] - before["lng"])
    return {
        "lat": round(lat, 7),
        "lng": round(lng, 7),
        "method": "linear_interpolation_between_predial_centroids",
        "target_plate": target,
        "before": before,
        "after": after,
        "before_plate": before_n,
        "after_plate": after_n,
        "t": round(t, 4),
    }


def pick_bracketing(records: list[dict], via_token: str, target: int) -> dict:
    parsed = []
    for rec in records:
        if rec["lat"] is None:
            continue
        n = parse_placa(rec["direccion"] or "", via_token)
        if n is None:
            continue
        parsed.append((n, rec))
    # unique by plate keeping closest to mean of duplicates
    by_plate: dict[int, dict] = {}
    for n, rec in parsed:
        by_plate.setdefault(n, rec)
    lowers = sorted([(n, r) for n, r in by_plate.items() if n < target], key=lambda x: x[0])
    uppers = sorted([(n, r) for n, r in by_plate.items() if n > target], key=lambda x: x[0])
    if not lowers or not uppers:
        return {
            "ok": False,
            "reason": "insufficient_bracketing_predios",
            "plates_found": sorted(by_plate.keys()),
            "records_considered": len(parsed),
        }
    before_n, before = lowers[-1]
    after_n, after = uppers[0]
    return {
        "ok": True,
        "interpolation": interpolate(before, after, target, before_n, after_n),
        "plates_found": sorted(by_plate.keys()),
    }


def spatial_near(lat: float, lng: float, meters: float = 120) -> tuple[list[dict], str]:
    dlat = meters / 111000.0
    dlng = meters / (111000.0 * max(abs(math.cos(math.radians(lat))), 1e-6))
    envelope = json.dumps(
        {
            "xmin": lng - dlng,
            "ymin": lat - dlat,
            "xmax": lng + dlng,
            "ymax": lat + dlat,
            "spatialReference": {"wkid": 4326},
        }
    )
    data, url = query(
        geometry=envelope,
        geometryType="esriGeometryEnvelope",
        inSR="4326",
        spatialRel="esriSpatialRelIntersects",
    )
    feats = data.get("features") or []
    out = []
    seen = set()
    for f in feats:
        rec = feature_record(f, url)
        key = (rec["objectid"], rec["direccion"])
        if key in seen or rec["lat"] is None:
            continue
        seen.add(key)
        rec["dist_to_query_m"] = round(haversine_m(lat, lng, rec["lat"], rec["lng"]), 1)
        out.append(rec)
    out.sort(key=lambda r: r["dist_to_query_m"])
    return out, url


def main() -> None:
    rows = list(csv.DictReader(CSV_PATH.open(encoding="utf-8-sig", newline="")))
    by_id = {r["id"]: r for r in rows if r["validation_status"] == "approximate_not_confirmed"}
    assert len(by_id) == 12

    probe: dict = {"service": SERVICE, "layer": "NOMENCLATURA PREDIAL", "queries": {}}

    # 1) Exact matches
    exact_targets = {
        "cda-manizales-cda-caldas-el-bosque-a730920403": "C 12 30 32",
        "cda-manizales-centro-de-diagnostico-automotor-motolina-0ce021ad5c": "CR 24 32 49",
        "cea-manizales-centro-de-ensenanza-automovilistica-cald-3e6c3b1930": "K 24 53 20",
        "cia-manizales-centro-integral-de-atencion-rutas-de-col-e89cbc963e": "C 21 19 27",
    }
    # Also try variants for CEA Caldas which appeared as 'K 24 53 20 K 25'
    exact_variants = {
        "cea-manizales-centro-de-ensenanza-automovilistica-cald-3e6c3b1930": [
            "K 24 53 20",
            "K 24 53 20 K 25",
            "CR 24 53 20",
        ],
        "cda-manizales-centro-de-diagnostico-automotor-motolina-0ce021ad5c": [
            "CR 24 32 49",
            "K 24 32 49",
        ],
    }

    geoportal_by_id: dict[str, dict] = {}

    for sid, addr in exact_targets.items():
        variants = exact_variants.get(sid, [addr])
        chosen = None
        all_hits = []
        urls = []
        for v in variants:
            hits, url = fetch_exact(v)
            urls.append(url)
            for h in hits:
                all_hits.append(h)
            if hits and chosen is None:
                # Prefer exact address string match to primary target when possible
                for h in hits:
                    if (h["direccion"] or "").strip().upper() == addr.upper() or v == addr:
                        chosen = h
                        break
                if chosen is None:
                    chosen = hits[0]
        # Dedup
        uniq = []
        seen = set()
        for h in all_hits:
            key = (h["objectid"], h["direccion"])
            if key in seen:
                continue
            seen.add(key)
            uniq.append(h)
        if chosen is None and uniq:
            chosen = uniq[0]
        cur = by_id[sid]
        cur_lat, cur_lng = float(cur["lat"]), float(cur["lng"])
        sec = SECONDARY.get(sid)
        geoportal_by_id[sid] = {
            "match_type": "exact" if chosen else "insufficient",
            "requested_address": addr,
            "variants_tried": variants,
            "feature": chosen,
            "all_features": uniq,
            "query_urls": urls,
            "distance_to_current_m": (
                None
                if not chosen
                else round(haversine_m(cur_lat, cur_lng, chosen["lat"], chosen["lng"]), 1)
            ),
            "distance_to_secondary_m": (
                None
                if not chosen or not sec
                else round(haversine_m(sec[0], sec[1], chosen["lat"], chosen["lng"]), 1)
            ),
            "recommended_status": (
                "candidate_for_confirmed_address_using_geoportal_geometry"
                if chosen
                else "keep_approximate_not_confirmed"
            ),
            "recommended_lat": None if not chosen else chosen["lat"],
            "recommended_lng": None if not chosen else chosen["lng"],
            "reason": (
                "Geometría centroide del predio oficial con dirección coincidente."
                if chosen
                else "No se encontró feature exacto."
            ),
        }
        probe["queries"][sid] = geoportal_by_id[sid]

    # 2) Academia Piloto — bracket 15-40 on Carrera 21
    piloto_id = "cea-manizales-academia-automovilistica-piloto-177f760536"
    piloto_recs, piloto_url = fetch_like("%K 21 15%", limit=100)
    piloto_recs2, piloto_url2 = fetch_like("%CR 21 15%", limit=100)
    piloto_all = { (r["objectid"], r["direccion"]): r for r in piloto_recs + piloto_recs2 }
    piloto_list = list(piloto_all.values())
    bracket = pick_bracketing(piloto_list, "K 21 15", 40)
    cur = by_id[piloto_id]
    cur_lat, cur_lng = float(cur["lat"]), float(cur["lng"])
    sec = SECONDARY[piloto_id]
    if bracket.get("ok"):
        inter = bracket["interpolation"]
        geoportal_by_id[piloto_id] = {
            "match_type": "interpolated",
            "requested_address": "CARRERA 21 NO. 15-40",
            "via_token": "K 21 15",
            "target_plate": 40,
            "features_used": [inter["before"], inter["after"]],
            "interpolation": inter,
            "plates_found": bracket["plates_found"],
            "query_urls": [piloto_url, piloto_url2],
            "distance_to_current_m": round(
                haversine_m(cur_lat, cur_lng, inter["lat"], inter["lng"]), 1
            ),
            "distance_to_secondary_m": round(
                haversine_m(sec[0], sec[1], inter["lat"], inter["lng"]), 1
            ),
            "recommended_status": "candidate_approximate_or_address_via_municipal_interpolation",
            "recommended_lat": inter["lat"],
            "recommended_lng": inter["lng"],
            "reason": (
                f"Interpolación entre placas {inter['before_plate']} y {inter['after_plate']} "
                f"sobre K 21 15 (no existe predio exacto 15-40)."
            ),
        }
    else:
        geoportal_by_id[piloto_id] = {
            "match_type": "insufficient",
            "requested_address": "CARRERA 21 NO. 15-40",
            "plates_found": bracket.get("plates_found"),
            "records": piloto_list[:20],
            "query_urls": [piloto_url, piloto_url2],
            "recommended_status": "keep_approximate_not_confirmed",
            "recommended_lat": None,
            "recommended_lng": None,
            "reason": bracket.get("reason"),
            "distance_to_current_m": None,
            "distance_to_secondary_m": None,
        }
    probe["queries"][piloto_id] = geoportal_by_id[piloto_id]

    # 3) CIA Eje Cafetero — bracket 21-40 on Carrera 20
    eje_id = "cia-manizales-centro-integral-de-atencion-eje-cafetero-3000df8047"
    eje1, eje_url1 = fetch_like("%K 20 21%", limit=100)
    eje2, eje_url2 = fetch_like("%CR 20 21%", limit=100)
    eje_all = {(r["objectid"], r["direccion"]): r for r in eje1 + eje2}
    eje_list = list(eje_all.values())
    bracket = pick_bracketing(eje_list, "K 20 21", 40)
    cur = by_id[eje_id]
    cur_lat, cur_lng = float(cur["lat"]), float(cur["lng"])
    sec = SECONDARY[eje_id]
    if bracket.get("ok"):
        inter = bracket["interpolation"]
        geoportal_by_id[eje_id] = {
            "match_type": "interpolated",
            "requested_address": "CARRERA 20 NO.21-40",
            "via_token": "K 20 21",
            "target_plate": 40,
            "features_used": [inter["before"], inter["after"]],
            "interpolation": inter,
            "plates_found": bracket["plates_found"],
            "query_urls": [eje_url1, eje_url2],
            "distance_to_current_m": round(
                haversine_m(cur_lat, cur_lng, inter["lat"], inter["lng"]), 1
            ),
            "distance_to_secondary_m": round(
                haversine_m(sec[0], sec[1], inter["lat"], inter["lng"]), 1
            ),
            "recommended_status": "candidate_approximate_or_address_via_municipal_interpolation",
            "recommended_lat": inter["lat"],
            "recommended_lng": inter["lng"],
            "reason": (
                f"Interpolación entre placas {inter['before_plate']} y {inter['after_plate']} "
                f"sobre K 20 21 (no existe predio exacto 21-40)."
            ),
        }
    else:
        geoportal_by_id[eje_id] = {
            "match_type": "insufficient",
            "requested_address": "CARRERA 20 NO.21-40",
            "plates_found": bracket.get("plates_found"),
            "sample_addresses": sorted({r["direccion"] for r in eje_list})[:30],
            "query_urls": [eje_url1, eje_url2],
            "recommended_status": "keep_approximate_not_confirmed",
            "recommended_lat": None,
            "recommended_lng": None,
            "reason": bracket.get("reason"),
            "distance_to_current_m": None,
            "distance_to_secondary_m": None,
        }
    probe["queries"][eje_id] = geoportal_by_id[eje_id]

    # 4) CEA Practicar — Alta Suiza / Cra 23 / Calle 70 / 70-59
    practicar_id = "cea-manizales-cea-practicar-del-eje-manizales-71a9a35cf0"
    # Search text patterns around calle 70 / carrera 23
    patterns = [
        "%C 70 23%",
        "%CL 70 23%",
        "%K 23 70%",
        "%CR 23 70%",
        "%AV 23 70%",
        "%C 70%",
    ]
    practicar_hits = []
    practicar_urls = []
    for p in patterns:
        hits, url = fetch_like(p, limit=100)
        practicar_urls.append(url)
        practicar_hits.extend(hits)
    # Also spatial around secondary sector and around calle70/cra23 guess
    near_sector, url_sec = spatial_near(5.0517, -75.4844, 180)
    practicar_urls.append(url_sec)
    # Filter addresses mentioning 70 and 23 or 70-59
    def relevant(rec: dict) -> bool:
        d = (rec.get("direccion") or "").upper()
        return ("70" in d and ("23" in d or "SANTANDER" in d or "AV" in d)) or "70 59" in d or "70-59" in d

    combined = {(r["objectid"], r["direccion"]): r for r in practicar_hits + near_sector}
    relevant_recs = [r for r in combined.values() if relevant(r) and r["lat"] is not None]
    # Try bracketing on several via tokens
    bracket_try = None
    for via in ["K 23 70", "CR 23 70", "C 70 23", "CL 70 23"]:
        # remap CR->K CL->C in parse
        via_norm = via.replace("CR ", "K ").replace("CL ", "C ")
        b = pick_bracketing(relevant_recs, via_norm, 59)
        if b.get("ok"):
            bracket_try = (via_norm, b)
            break
    # Also try plates on C 70 with cra 23 in address string
    if bracket_try is None:
        # parse numbers after 'C 70' or 'K 23'
        for via_norm in ["C 70", "K 23"]:
            b = pick_bracketing(relevant_recs, via_norm, 59)
            if b.get("ok"):
                # verify interpolated point not near Cerro de Oro current (lng ~ -75.476)
                inter = b["interpolation"]
                if inter["lng"] < -75.480:  # more west toward Alta Suiza / Av Santander
                    bracket_try = (via_norm, b)
                    break

    cur = by_id[practicar_id]
    cur_lat, cur_lng = float(cur["lat"]), float(cur["lng"])
    sec = SECONDARY[practicar_id]
    if bracket_try:
        via_norm, b = bracket_try
        inter = b["interpolation"]
        # Confirm not Cerro de Oro: current bad point ~ -75.4765; Alta Suiza candidate ~ -75.484
        in_alta = inter["lng"] <= -75.480 and inter["lat"] < 5.06
        geoportal_by_id[practicar_id] = {
            "match_type": "interpolated",
            "requested_address": "CRA 23 NRO 70-59 ALTA SUIZA - AVENIDA SANTANDER",
            "via_token": via_norm,
            "target_plate": 59,
            "features_used": [inter["before"], inter["after"]],
            "interpolation": inter,
            "plates_found": b["plates_found"],
            "alta_suiza_plausible": in_alta,
            "not_cerro_de_oro": inter["lng"] < -75.478,
            "query_urls": practicar_urls,
            "sample_relevant_addresses": sorted({r["direccion"] for r in relevant_recs})[:40],
            "distance_to_current_m": round(
                haversine_m(cur_lat, cur_lng, inter["lat"], inter["lng"]), 1
            ),
            "distance_to_secondary_m": round(
                haversine_m(sec[0], sec[1], inter["lat"], inter["lng"]), 1
            ),
            "recommended_status": "approximate_not_confirmed_with_corrected_municipal_interpolation",
            "recommended_lat": inter["lat"],
            "recommended_lng": inter["lng"],
            "reason": (
                "Interpolación municipal hacia 70-59; mantener approximate_not_confirmed "
                "salvo predio exacto. Verificar sector Alta Suiza."
            ),
        }
    else:
        # Exact 70-59?
        exact_7059 = [r for r in relevant_recs if re.search(r"70\s*[- ]\s*59|70 59", (r["direccion"] or ""), re.I)]
        if exact_7059:
            chosen = exact_7059[0]
            geoportal_by_id[practicar_id] = {
                "match_type": "exact",
                "feature": chosen,
                "recommended_lat": chosen["lat"],
                "recommended_lng": chosen["lng"],
                "distance_to_current_m": round(
                    haversine_m(cur_lat, cur_lng, chosen["lat"], chosen["lng"]), 1
                ),
                "distance_to_secondary_m": round(
                    haversine_m(sec[0], sec[1], chosen["lat"], chosen["lng"]), 1
                ),
                "recommended_status": "candidate_for_confirmed_address_using_geoportal_geometry",
                "reason": "Predio exacto 70-59 encontrado.",
                "query_urls": practicar_urls,
            }
        else:
            geoportal_by_id[practicar_id] = {
                "match_type": "insufficient",
                "requested_address": "CRA 23 NRO 70-59 ALTA SUIZA",
                "sample_relevant_addresses": sorted({r["direccion"] for r in relevant_recs})[:40],
                "near_sector_top": near_sector[:15],
                "query_urls": practicar_urls,
                "recommended_status": "keep_approximate_not_confirmed_current_inconsistent",
                "recommended_lat": None,
                "recommended_lng": None,
                "distance_to_current_m": None,
                "distance_to_secondary_m": None,
                "reason": (
                    "No se hallaron predios que encierren 70-59 de forma coherente en Alta Suiza; "
                    "coordenada CSV actual sigue marcada inconsistente (Cerro de Oro)."
                ),
            }
    probe["queries"][practicar_id] = geoportal_by_id[practicar_id]

    # 5) Evaluando — document only
    eval_id = "crc-manizales-centro-de-reconocimiento-de-conductores--dfb8fe156d"
    geoportal_by_id[eval_id] = {
        "match_type": "documentation_only",
        "recommended_lat": None,
        "recommended_lng": None,
        "distance_to_current_m": None,
        "distance_to_secondary_m": None,
        "secondary_reference_not_applied": list(SECONDARY[eval_id]),
        "recommended_status": "operational_status_requires_review_no_coord_change",
        "reason": (
            "Sin cambio de coordenadas/estado. RUNT directorio clásico: Calle 22 #18-29 piso 2; "
            "ausente en RUNT 2.0 actores activos/certificando 2026 (hallazgo auditoría)."
        ),
        "runt_discrepancy": {
            "classic_directory_address": "CALLE 22 NO. 18-29 PISO 2",
            "runt_2_0_active_certifying_2026": "not_listed_per_external_audit",
            "action": "document_only",
        },
    }
    probe["queries"][eval_id] = geoportal_by_id[eval_id]

    # 6) Unchanged
    unchanged = {
        "cda-manizales-cda-socicar-7acac31f0f": "keep_approximate_insufficient_evidence",
        "cea-manizales-academia-automovilistica-caldas-sas-12d613c393": "keep_approximate_bad_commercial_poi",
        "cia-manizales-cimyc-manizales-s-a-s-498175000a": "keep_approximate_insufficient_evidence",
        "crc-manizales-certificamos-agustinos-98839ab670": "keep_approximate_shared_nit_separate_sites",
    }
    for sid, decision in unchanged.items():
        notes = {
            "cda-manizales-cda-socicar-7acac31f0f": "Sin evidencia de punto exacto.",
            "cea-manizales-academia-automovilistica-caldas-sas-12d613c393": (
                "POI comercial del centro mal georreferenciado; no usar."
            ),
            "cia-manizales-cimyc-manizales-s-a-s-498175000a": "Sin evidencia de punto exacto.",
            "crc-manizales-certificamos-agustinos-98839ab670": (
                "Comparte NIT con Certificamos Terminal; sedes distintas, no fusionar."
            ),
        }
        geoportal_by_id[sid] = {
            "match_type": "insufficient",
            "recommended_lat": None,
            "recommended_lng": None,
            "distance_to_current_m": None,
            "distance_to_secondary_m": None,
            "recommended_status": decision,
            "reason": notes[sid],
            "unchanged_this_round": True,
        }

    # Build inventory rows + table
    out_rows = []
    table = []
    for i, r in enumerate(
        [by_id[k] for k in sorted(by_id.keys(), key=lambda x: list(by_id.keys()).index(x))]
        if False
        else list(csv.DictReader(CSV_PATH.open(encoding="utf-8-sig", newline="")))
    ):
        pass

    # Preserve original CSV order of approximate rows
    approx = [
        r
        for r in csv.DictReader(CSV_PATH.open(encoding="utf-8-sig", newline=""))
        if r["validation_status"] == "approximate_not_confirmed"
    ]
    for i, r in enumerate(approx, 1):
        sid = r["id"]
        g = geoportal_by_id[sid]
        cur_lat, cur_lng = float(r["lat"]), float(r["lng"])
        sec = SECONDARY.get(sid)
        phone = (r.get("phone") or "").strip()
        nit = (r.get("nit") or "").strip()
        feat = g.get("feature")
        feats_used = g.get("features_used") or ([feat] if feat else [])
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
                "query_urls": g.get("query_urls") or ([feat["query_url"]] if feat and feat.get("query_url") else []),
                "service": SERVICE,
                "detail": {k: v for k, v in g.items() if k not in {"all_features", "records", "near_sector_top"}},
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
        "",
        "## Tabla final",
        "",
        "| ID | Dirección RUNT | Actual | Secundaria | Geoportal/interpolación | Tipo | OBJECTIDs | Estado recomendado | Motivo |",
        "|---|---|---|---|---|---|---|---|---|",
    ]
    for t in table:
        short = t["id"].split("-")[-1][:10] + "…"
        oids = ",".join(str(x) for x in t["objectids"]) if t["objectids"] else "—"
        lines.append(
            f"| `{t['id'][-32:]}` | {t['address_runt']} | {t['lat_lng_current']} | "
            f"{t['lat_lng_secondary']} | {t['lat_lng_geoportal_or_interpolation']} | "
            f"`{t['match_type']}` | {oids} | `{t['recommended_status']}` | {t['reason']} |"
        )
    lines.append("")
    for row in out_rows:
        lines += [
            f"## {row['n']}. {row['name']} ({row['kind']})",
            "",
            f"- **ID:** `{row['id']}`",
            f"- **Dirección RUNT:** {row['address_runt']}",
            f"- **Actual:** {row['lat_current']}, {row['lng_current']}",
            f"- **Secundaria:** {row['secondary_reference']}",
            f"- **Geoportal/interpolación:** {row['geoportal_or_interpolation'].get('lat')}, {row['geoportal_or_interpolation'].get('lng')}",
            f"- **Tipo:** `{row['geoportal_or_interpolation'].get('match_type')}`",
            f"- **OBJECTIDs:** {row['geoportal_or_interpolation'].get('objectids')}",
            f"- **Dist. a actual:** {row['distance_current_to_geoportal_m']} m",
            f"- **Dist. a secundaria:** {row['distance_secondary_to_geoportal_m']} m",
            f"- **Estado recomendado:** `{row['recommended_status']}`",
            f"- **Motivo:** {row['reason']}",
            f"- **URLs:** {row['geoportal_or_interpolation'].get('query_urls')}",
            "",
        ]
    OUT_MD.write_text("\n".join(lines), encoding="utf-8")
    print(json.dumps({"rows": len(out_rows), "out": str(OUT_JSON)}, indent=2))
    for t in table:
        print(
            t["match_type"],
            t["id"][-28:],
            t["lat_lng_geoportal_or_interpolation"],
            t["objectids"],
        )


if __name__ == "__main__":
    main()
