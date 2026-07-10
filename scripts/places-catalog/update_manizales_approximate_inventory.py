"""Rebuild Manizales approximate audit inventory with external findings + Geoportal checks."""
from __future__ import annotations

import csv
import json
import math
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
GEOPORTAL_LAYER = (
    "https://sig.manizales.gov.co/wadmzl/rest/services/20_WEB/"
    "2020_consulta_POT_urbano_web_v10_2/MapServer/10"
)


def haversine_m(lat1: float, lng1: float, lat2: float, lng2: float) -> float:
    r = 6371000.0
    p1, p2 = math.radians(lat1), math.radians(lat2)
    dp = math.radians(lat2 - lat1)
    dl = math.radians(lng2 - lng1)
    a = math.sin(dp / 2) ** 2 + math.cos(p1) * math.cos(p2) * math.sin(dl / 2) ** 2
    return 2 * r * math.asin(math.sqrt(a))


# External audit findings (CSV not modified).
FINDINGS: dict[str, dict] = {
    "cda-manizales-cda-caldas-el-bosque-a730920403": {
        "decision": "candidate_confirmed_address",
        "candidate_lat": 5.0619350,
        "candidate_lng": -75.5238599,
        "status_note": "Candidato fuerte de dirección; estado CSV sigue approximate_not_confirmed.",
        "blocking": "Aplicar al CSV solo tras decisión explícita de apply/auditoría.",
        "audit_notes": [
            "Candidato de dirección propuesto por auditoría externa.",
        ],
        "geoportal": {
            "accessible": True,
            "matched_predial_address": "C 12 30 32",
            "match_quality": "exact_or_equivalent",
            "nearest_predial_distance_m": 13.1,
            "detail": "Capa NOMENCLATURA PREDIAL devolvió 'C 12 30 32' a ~13 m del candidato.",
        },
    },
    "cda-manizales-cda-socicar-7acac31f0f": {
        "decision": "keep_approximate_insufficient_evidence",
        "candidate_lat": None,
        "candidate_lng": None,
        "status_note": "Continúa aproximado por falta de evidencia de punto exacto.",
        "blocking": "Falta pin comercial/municipal verificable coherente con nombre+dirección.",
        "audit_notes": [
            "Sin candidato fuerte de dirección en esta ronda.",
        ],
        "geoportal": {"accessible": True, "queried": False, "detail": "No se consultó candidato nuevo."},
    },
    "cda-manizales-centro-de-diagnostico-automotor-motolina-0ce021ad5c": {
        "decision": "candidate_confirmed_address",
        "candidate_lat": 5.0667890,
        "candidate_lng": -75.5108139,
        "status_note": "Candidato fuerte de dirección; estado CSV sigue approximate_not_confirmed.",
        "blocking": "Aplicar al CSV solo tras decisión explícita de apply/auditoría.",
        "audit_notes": [
            "Candidato de dirección propuesto por auditoría externa.",
        ],
        "geoportal": {
            "accessible": True,
            "matched_predial_address": "CR 24 32 49",
            "match_quality": "exact_or_equivalent",
            "nearest_predial_distance_m": 8.6,
            "detail": "NOMENCLATURA PREDIAL: 'CR 24 32 49' a ~8.6 m del candidato (coincide con RUNT).",
        },
    },
    "cea-manizales-academia-automovilistica-caldas-sas-12d613c393": {
        "decision": "keep_approximate_bad_commercial_poi",
        "candidate_lat": None,
        "candidate_lng": None,
        "status_note": "POI comercial encontrado está mal georreferenciado en el centro; no usarlo.",
        "blocking": "Conservar punto actual aproximado hasta evidencia municipal/comercial válida.",
        "audit_notes": [
            "Registrar POI comercial del centro como mal georreferenciado.",
            "No adoptar esas coordenadas.",
            "Conservar lat/lng actuales del CSV.",
        ],
        "geoportal": {"accessible": True, "queried": False, "detail": "Sin candidato nuevo a validar."},
    },
    "cea-manizales-academia-automovilistica-piloto-177f760536": {
        "decision": "candidate_confirmed_address",
        "candidate_lat": 5.0682222,
        "candidate_lng": -75.5217211,
        "status_note": "Candidato fuerte de dirección; estado CSV sigue approximate_not_confirmed.",
        "blocking": "Aplicar al CSV solo tras decisión explícita; predial exacto 15-40 no hallado.",
        "audit_notes": [
            "Candidato de dirección propuesto por auditoría externa.",
        ],
        "geoportal": {
            "accessible": True,
            "matched_predial_address": "K 21 15 38 (cercano; no existe 'K 21 15 40' exacto)",
            "match_quality": "nearby_same_block",
            "nearest_predial_distance_m": 8.9,
            "detail": "Predios en K 21 15 38 / 44-48 / 60 cerca del candidato; sin ficha exacta 15-40.",
        },
    },
    "cea-manizales-cea-practicar-del-eje-manizales-71a9a35cf0": {
        "decision": "current_coordinate_inconsistent",
        "candidate_lat": 5.0517,
        "candidate_lng": -75.4844,
        "candidate_kind": "approximate_sector_only",
        "status_note": (
            "Coordenada actual incoherente (Cerro de Oro/Colseguros, no Alta Suiza). "
            "Sector candidato aproximado sobre Av. Santander/Cra 23; sigue approximate."
        ),
        "blocking": "Necesita coordenada municipal o comercial verificable en Alta Suiza antes de confirmar.",
        "audit_notes": [
            "Punto CSV actual cae fuera del sector declarado (Alta Suiza - Av. Santander).",
            "Sector candidato 5.0517,-75.4844 es solo aproximación de zona, no confirmación.",
        ],
        "geoportal": {
            "accessible": True,
            "queried": False,
            "detail": "No se validó como confirmed_address; sector aproximado pendiente de nomenclatura exacta 70-59.",
        },
    },
    "cea-manizales-centro-de-ensenanza-automovilistica-cald-3e6c3b1930": {
        "decision": "candidate_confirmed_address",
        "candidate_lat": 5.0628630,
        "candidate_lng": -75.4961049,
        "status_note": "Candidato fuerte de dirección; estado CSV sigue approximate_not_confirmed.",
        "blocking": "Aplicar al CSV solo tras decisión explícita de apply/auditoría.",
        "audit_notes": [
            "Candidato de dirección propuesto por auditoría externa.",
        ],
        "geoportal": {
            "accessible": True,
            "matched_predial_address": "K 24 53 20 K 25",
            "match_quality": "exact_or_equivalent",
            "nearest_predial_distance_m": 7.0,
            "detail": "NOMENCLATURA PREDIAL: 'K 24 53 20 K 25' a ~7 m (coincide con CRA 24 53-20).",
        },
    },
    "cia-manizales-centro-integral-de-atencion-rutas-de-col-e89cbc963e": {
        "decision": "candidate_confirmed_address",
        "candidate_lat": 5.0694020,
        "candidate_lng": -75.5182809,
        "status_note": "Candidato fuerte de dirección; estado CSV sigue approximate_not_confirmed.",
        "blocking": "Aplicar al CSV solo tras decisión explícita de apply/auditoría.",
        "audit_notes": [
            "Candidato de dirección propuesto por auditoría externa.",
        ],
        "geoportal": {
            "accessible": True,
            "matched_predial_address": "C 21 19 27",
            "match_quality": "exact_or_equivalent",
            "nearest_predial_distance_m": 20.9,
            "detail": "NOMENCLATURA PREDIAL: 'C 21 19 27' a ~21 m del candidato (coincide con RUNT).",
        },
    },
    "cia-manizales-centro-integral-de-atencion-eje-cafetero-3000df8047": {
        "decision": "candidate_confirmed_address",
        "candidate_lat": 5.0689636,
        "candidate_lng": -75.5181746,
        "status_note": "Candidato fuerte de dirección; estado CSV sigue approximate_not_confirmed.",
        "blocking": "Aplicar al CSV solo tras decisión explícita; predial exacto 21-40 no hallado.",
        "audit_notes": [
            "Candidato de dirección propuesto por auditoría externa.",
        ],
        "geoportal": {
            "accessible": True,
            "matched_predial_address": "K 20 21 35 (cercano; no existe 'K 20 21 40' exacto)",
            "match_quality": "nearby_same_block",
            "nearest_predial_distance_m": 3.9,
            "detail": "Predios K 20 21 35 y tramos C 21 20 cerca del candidato; sin ficha exacta 21-40.",
        },
    },
    "cia-manizales-cimyc-manizales-s-a-s-498175000a": {
        "decision": "keep_approximate_insufficient_evidence",
        "candidate_lat": None,
        "candidate_lng": None,
        "status_note": "Continúa aproximado por falta de evidencia de punto exacto.",
        "blocking": "Falta pin comercial/municipal verificable.",
        "audit_notes": [
            "Sin candidato fuerte de dirección en esta ronda.",
        ],
        "geoportal": {"accessible": True, "queried": False, "detail": "No se consultó candidato nuevo."},
    },
    "crc-manizales-centro-de-reconocimiento-de-conductores--dfb8fe156d": {
        "decision": "operational_status_requires_review",
        "candidate_lat": 5.0700560,
        "candidate_lng": -75.5177019,
        "status_note": (
            "RUNT aún muestra Calle 22 #18-29 piso 2; no aparece en RUNT 2.0 actores "
            "activos/certificando 2026. Coordenada de referencia registrada; CSV sin cambio."
        ),
        "blocking": "Revisar estado operativo/presencia RUNT 2.0 antes de confirmar o retirar.",
        "audit_notes": [
            "Dirección RUNT vigente en directorio clásico: Calle 22 #18-29 piso 2.",
            "Ausente del conjunto RUNT 2.0 activos/certificando 2026 (hallazgo de auditoría).",
            "Coordenada de referencia 5.0700560,-75.5177019 (no aplicada al CSV).",
        ],
        "geoportal": {
            "accessible": True,
            "matched_predial_address": "C 22 18 23 29",
            "match_quality": "exact_or_equivalent",
            "nearest_predial_distance_m": 2.8,
            "detail": "NOMENCLATURA PREDIAL: 'C 22 18 23 29' a ~2.8 m de la referencia (cubre 18-29).",
        },
    },
    "crc-manizales-certificamos-agustinos-98839ab670": {
        "decision": "keep_approximate_insufficient_evidence",
        "candidate_lat": None,
        "candidate_lng": None,
        "status_note": (
            "Continúa aproximado por falta de evidencia de punto exacto. "
            "Comparte NIT con Certificamos Terminal; son dos sedes RUNT distintas (no fusionar)."
        ),
        "blocking": "Falta pin exacto de la sede Agustinos; no fusionar con Terminal.",
        "audit_notes": [
            "NIT compartido con Certificamos Terminal.",
            "Dos sedes RUNT diferentes: no fusionar registros ni coordenadas.",
        ],
        "geoportal": {"accessible": True, "queried": False, "detail": "No se consultó candidato nuevo."},
    },
}


def main() -> None:
    rows = list(csv.DictReader(CSV_PATH.open(encoding="utf-8-sig", newline="")))
    approx = [r for r in rows if r["validation_status"] == "approximate_not_confirmed"]
    if len(approx) != 12:
        raise SystemExit(f"expected approximate rows, got {len(approx)}")

    out_rows: list[dict] = []
    table: list[dict] = []
    for i, r in enumerate(approx, 1):
        sid = r["id"]
        finding = FINDINGS[sid]
        cur_lat, cur_lng = float(r["lat"]), float(r["lng"])
        cand_lat = finding.get("candidate_lat")
        cand_lng = finding.get("candidate_lng")
        dist = None
        if cand_lat is not None and cand_lng is not None:
            dist = round(haversine_m(cur_lat, cur_lng, float(cand_lat), float(cand_lng)), 1)

        phone = (r.get("phone") or "").strip()
        nit = (r.get("nit") or "").strip()
        item = {
            "n": i,
            "id": sid,
            "kind": r["kind"],
            "name": r["name"],
            "address_runt": r["address"],
            "city": r["city"],
            "nit": nit or None,
            "phone": None if phone in {"", "0"} else phone,
            "lat_current": cur_lat,
            "lng_current": cur_lng,
            "precision": r["precision"],
            "confidence": float(r["confidence"]),
            "provider": r["provider"],
            "evidence_current": r.get("evidence") or "",
            "csv_validation_status": r["validation_status"],
            "csv_modified": False,
            "decision": finding["decision"],
            "candidate_lat": cand_lat,
            "candidate_lng": cand_lng,
            "candidate_kind": finding.get("candidate_kind", "address_candidate"),
            "distance_current_to_candidate_m": dist,
            "status_note": finding["status_note"],
            "blocking_pending": finding["blocking"],
            "audit_notes": finding["audit_notes"],
            "geoportal_manizales": {
                "layer": GEOPORTAL_LAYER,
                "layer_name": "NOMENCLATURA PREDIAL",
                **finding["geoportal"],
            },
            "sources_consulted": [
                "CSV canónico geocodes_manizales_validado.csv (sin modificar)",
                "Hallazgos de auditoría externa (esta ronda)",
                f"Geoportal Alcaldía de Manizales — {GEOPORTAL_LAYER}",
            ],
        }
        out_rows.append(item)
        table.append(
            {
                "id": sid,
                "decision": finding["decision"],
                "lat_lng_current": f"{cur_lat},{cur_lng}",
                "lat_lng_candidate": (
                    f"{cand_lat},{cand_lng}" if cand_lat is not None else "—"
                ),
                "distance_m": dist if dist is not None else "—",
                "source": "Geoportal NOMENCLATURA PREDIAL + auditoría externa",
                "csv_status": "approximate_not_confirmed (sin cambio)",
                "blocking_pending": finding["blocking"],
            }
        )

    payload = {
        "city": "Manizales",
        "validation_status_in_csv": "approximate_not_confirmed",
        "count": len(out_rows),
        "canonical_csv": str(CSV_PATH).replace("\\", "/"),
        "canonical_csv_modified": False,
        "expected_scope_counts_unchanged": True,
        "geoportal": {
            "accessible": True,
            "service": GEOPORTAL_LAYER,
            "note": (
                "Consultas espaciales/textuales a NOMENCLATURA PREDIAL. "
                "No se usó geocodificador secundario como proveedor persistente."
            ),
        },
        "decision_legend": {
            "candidate_confirmed_address": (
                "Candidato fuerte de dirección registrado; CSV aún approximate_not_confirmed."
            ),
            "current_coordinate_inconsistent": (
                "Coordenada CSV incoherente con la dirección/sector RUNT."
            ),
            "keep_approximate_bad_commercial_poi": (
                "POI comercial descartado por mala georreferencia; conservar aproximado."
            ),
            "operational_status_requires_review": (
                "Revisar vigencia operativa (RUNT 2.0) antes de confirmar."
            ),
            "keep_approximate_insufficient_evidence": (
                "Sin evidencia de punto exacto; conservar aproximado."
            ),
        },
        "rows": out_rows,
        "summary_table": table,
    }
    OUT_JSON.write_text(json.dumps(payload, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")

    lines = [
        "# Inventario actualizado — Manizales `approximate_not_confirmed` (12)",
        "",
        "**CSV canónico no modificado.** Conteos del scope sin cambiar.",
        "",
        "Geoportal consultado: capa `NOMENCLATURA PREDIAL` del SIG Alcaldía de Manizales "
        f"(`{GEOPORTAL_LAYER}`).",
        "",
        "## Tabla resumen",
        "",
        "| ID | Decisión | Actual | Candidata | Dist. m | Fuente | Estado CSV | Bloqueo pendiente |",
        "|---|---|---|---|---:|---|---|---|",
    ]
    for t in table:
        short = t["id"][-24:]
        lines.append(
            f"| `{short}` | `{t['decision']}` | {t['lat_lng_current']} | "
            f"{t['lat_lng_candidate']} | {t['distance_m']} | Geoportal+auditoría | "
            f"{t['csv_status']} | {t['blocking_pending']} |"
        )
    lines.append("")

    for row in out_rows:
        lines.extend(
            [
                f"## {row['n']}. {row['name']} ({row['kind']})",
                "",
                f"- **ID:** `{row['id']}`",
                f"- **Dirección RUNT:** {row['address_runt']}",
                f"- **Coordenadas actuales:** {row['lat_current']}, {row['lng_current']}",
                f"- **Candidata:** {row['candidate_lat']}, {row['candidate_lng']}"
                if row["candidate_lat"] is not None
                else "- **Candidata:** —",
                f"- **Distancia actual→candidata:** {row['distance_current_to_candidate_m']} m"
                if row["distance_current_to_candidate_m"] is not None
                else "- **Distancia actual→candidata:** —",
                f"- **Decisión:** `{row['decision']}`",
                f"- **Estado CSV:** `{row['csv_validation_status']}` (sin cambio)",
                f"- **Nota:** {row['status_note']}",
                f"- **Bloqueo pendiente:** {row['blocking_pending']}",
                f"- **Evidencia CSV actual:** {row['evidence_current']}",
                f"- **Geoportal:** {json.dumps(row['geoportal_manizales'], ensure_ascii=False)}",
                "- **Notas de auditoría:**",
            ]
        )
        for n in row["audit_notes"]:
            lines.append(f"  - {n}")
        lines.append("")

    OUT_MD.write_text("\n".join(lines), encoding="utf-8")
    print(f"wrote {OUT_JSON}")
    print(f"wrote {OUT_MD}")


if __name__ == "__main__":
    main()
