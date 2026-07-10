"""Generate Manizales approximate_not_confirmed review inventory (read-only)."""
from __future__ import annotations

import csv
import json
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


def main() -> None:
    rows = list(csv.DictReader(CSV_PATH.open(encoding="utf-8-sig", newline="")))
    approx = [r for r in rows if r["validation_status"] == "approximate_not_confirmed"]
    if len(approx) != 12:
        raise SystemExit(f"expected approximate rows, got {len(approx)}")

    out: list[dict] = []
    for i, r in enumerate(approx, 1):
        phone = (r.get("phone") or "").strip()
        nit = (r.get("nit") or "").strip()
        evidence = r.get("evidence") or ""
        ev = evidence.casefold()

        reasons: list[str] = []
        if "no confirma el negocio" in ev or "no coincidi" in ev:
            reasons.append(
                "El geocoder solo ancló vía/cruce o interpolación; "
                "no hubo match comercial verificable (nombre/teléfono)."
            )
        if r["precision"] in {"street_intersection", "street_interpolation"}:
            reasons.append(
                f"Precisión actual '{r['precision']}' no es rooftop/business/address confirmada."
            )
        if "quedó a" in ev or "quedo a" in ev:
            reasons.append(
                "Hubo candidato comercial lejano o inconsistente respecto al ancla RUNT."
            )
        if not reasons:
            reasons.append(
                "Marcada approximate_not_confirmed en el CSV validado; "
                "sin evidencia de negocio en el punto."
            )

        searches = [
            "Directorio RUNT / ficha del actor (nombre, dirección, NIT) y contraste con la dirección del CSV.",
            f"Búsqueda de nombre comercial exacto + Manizales: '{r['name']}'.",
            f"Búsqueda de dirección RUNT en mapas: '{r['address']}, Manizales, Caldas'.",
        ]
        if phone and phone != "0":
            searches.append(
                f"Verificar teléfono RUNT {phone} en Google/Maps/páginas del negocio "
                "(no usar IA como fuente)."
            )
        else:
            searches.append(
                "Sin teléfono usable en CSV (0/vacío): priorizar NIT + nombre en RUES/RUNT "
                "y sitio web oficial si existe."
            )
        if nit:
            searches.append(
                f"Consulta NIT {nit} en RUES / Cámara de Comercio (razón social y domicilio)."
            )
        searches.append(
            "Street View / foto de fachada o pin de Google Business Profile solo si el "
            "nombre/dirección coinciden de forma inequívoca."
        )
        searches.append(
            "Si no hay evidencia suficiente: conservar lat/lng actuales y mantener "
            "approximate_not_confirmed."
        )

        out.append(
            {
                "n": i,
                "id": r["id"],
                "kind": r["kind"],
                "name": r["name"],
                "address_runt": r["address"],
                "city": r["city"],
                "nit": nit or None,
                "phone": None if phone in {"", "0"} else phone,
                "lat": float(r["lat"]),
                "lng": float(r["lng"]),
                "precision": r["precision"],
                "confidence": float(r["confidence"]),
                "provider": r["provider"],
                "evidence_current": evidence,
                "runt_source_url": r.get("runt_source_url") or "",
                "geocode_source_url": r.get("geocode_source_url") or "",
                "why_still_approximate": " ".join(reasons),
                "sources_or_searches_needed": searches,
            }
        )

    payload = {
        "city": "Manizales",
        "validation_status": "approximate_not_confirmed",
        "count": len(out),
        "canonical_csv": str(CSV_PATH).replace("\\", "/"),
        "canonical_csv_modified": False,
        "rows": out,
        "rules": [
            "No inventar coordenadas.",
            "No convertir a confirmed solo por caer dentro del bbox de Manizales.",
            "Para confirmar: evidencia coherente (nombre, dirección, teléfono, NIT o fuente oficial).",
            "Sin evidencia suficiente: conservar coordenadas actuales.",
            "No usar respuestas de IA como fuente.",
            "No cambiar conteos esperados del scope hasta cerrar la auditoría.",
        ],
    }
    OUT_JSON.write_text(json.dumps(payload, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")

    lines = [
        "# Inventario — Manizales `approximate_not_confirmed` (12)",
        "",
        "Trabajo de auditoría externa. **CSV canónico no modificado.**",
        "",
        "Reglas: no inventar coordenadas; no confirmar solo por bbox; evidencia = nombre/dirección/teléfono/NIT/fuente oficial; sin evidencia → conservar punto actual; no usar IA como fuente.",
        "",
    ]
    for row in out:
        lines.extend(
            [
                f"## {row['n']}. {row['name']} ({row['kind']})",
                "",
                f"- **ID:** `{row['id']}`",
                f"- **Dirección RUNT:** {row['address_runt']}",
                f"- **Coordenadas actuales:** {row['lat']}, {row['lng']}",
                f"- **Precisión / confianza / provider:** {row['precision']} / {row['confidence']} / {row['provider']}",
                f"- **NIT:** {row['nit'] or '—'}",
                f"- **Teléfono:** {row['phone'] or '—'}",
                f"- **Evidencia actual:** {row['evidence_current']}",
                f"- **Por qué sigue aproximada:** {row['why_still_approximate']}",
                "- **Fuentes / búsquedas necesarias:**",
            ]
        )
        for s in row["sources_or_searches_needed"]:
            lines.append(f"  - {s}")
        lines.append("")

    OUT_MD.write_text("\n".join(lines), encoding="utf-8")
    print(f"wrote {OUT_JSON}")
    print(f"wrote {OUT_MD}")


if __name__ == "__main__":
    main()
