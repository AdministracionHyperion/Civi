#!/usr/bin/env python3
"""Normalize raw RUNT shards into places_colombia_sin_coords.json (no geocoding)."""

from __future__ import annotations

import argparse
import hashlib
import json
import re
import unicodedata
from collections import Counter, defaultdict
from datetime import datetime, timezone
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
RAW_DIR = ROOT / "data" / "places" / "raw"
OUT_JSON = ROOT / "data" / "places" / "places_colombia_sin_coords.json"
OUT_SUMMARY = ROOT / "data" / "places" / "places_colombia_summary.json"

CITY_ALIASES = {
    "BOGOTA": "Bogota",
    "BOGOTA D.C.": "Bogota",
    "BOGOTA, D.C.": "Bogota",
    "BOGOTA, D. C.": "Bogota",
    "BOGOTA D C": "Bogota",
    "MEDELLIN": "Medellin",
    "BUCARAMANGA": "Bucaramanga",
    "CALI": "Cali",
    "MANIZALES": "Manizales",
    "CUCUTA": "Cucuta",
    "IBAGUE": "Ibague",
}


def _strip_accents(value: str) -> str:
    return "".join(
        ch for ch in unicodedata.normalize("NFKD", value) if not unicodedata.combining(ch)
    )


def _title_city(value: str) -> str:
    key = re.sub(r"\s+", " ", _strip_accents(value or "").upper().strip())
    key = key.replace(",", "")
    if key in CITY_ALIASES:
        return CITY_ALIASES[key]
    return " ".join(part.capitalize() for part in key.lower().split())


def _title_dept(value: str) -> str:
    key = re.sub(r"\s+", " ", _strip_accents(value or "").upper().strip())
    specials = {
        "BOGOTA D.C.": "Bogota D.C.",
        "BOGOTA, D. C.": "Bogota D.C.",
        "BOGOTA, D.C.": "Bogota D.C.",
        "VALLE DEL CAUCA": "Valle del Cauca",
        "NORTE DE SANTANDER": "Norte de Santander",
        "N. DE SANTANDER": "Norte de Santander",
        "SAN ANDRES": "San Andres",
        "ARCHIPIELAGO DE SAN ANDRES, PROVIDENCIA": "San Andres",
        "ARCHIPIELAGO DE SAN ANDRES": "San Andres",
    }
    if key in specials:
        return specials[key]
    return " ".join(part.capitalize() for part in key.lower().split())


def _slug(value: str, *, max_len: int = 40) -> str:
    text = _strip_accents(value or "").lower()
    text = re.sub(r"[^a-z0-9]+", "-", text).strip("-")
    return text[:max_len] or "place"


def _make_id(kind: str, city: str, name: str, address: str, nit: str | None) -> str:
    base = f"{kind.lower()}-{_slug(city)}-{_slug(name)}"
    digest = hashlib.sha1(f"{kind}|{city}|{name}|{address}|{nit or ''}".encode("utf-8")).hexdigest()[:10]
    return f"{base}-{digest}"[:128]


def _looks_like_city_dept(text: str) -> bool:
    """True when text resembles 'BUCARAMANGA - SANTANDER', not an address fragment."""
    if " - " not in text:
        return False
    left, right = text.split(" - ", 1)
    left = left.strip()
    right = right.strip()
    if not left or not right:
        return False
    # Addresses often contain digits / # / Calle / Carrera
    if re.search(r"\d|#|CALLE|CARRERA|CRA|CL |AV |AVENIDA|KM ", _strip_accents(text).upper()):
        return False
    if len(left) > 40 or len(right) > 40:
        return False
    return True


def normalize_row(row: dict, target: dict, scraped_at: str) -> dict | None:
    name = (row.get("name") or "").strip()
    address = (row.get("address") or "").strip()
    if not name:
        return None

    kind = target["kind"]
    # Prefer authoritative target municipality/department from open-data + RUNT form
    city = _title_city(target.get("municipality") or "")
    department = _title_dept(target.get("department") or "")
    if city == "Bogota":
        department = "Bogota D.C."

    city_line = (row.get("city_line") or "").strip()
    if _looks_like_city_dept(city_line):
        left, right = city_line.split(" - ", 1)
        parsed_city = _title_city(left)
        parsed_dept = _title_dept(right)
        if parsed_city == "Bogota":
            parsed_dept = "Bogota D.C."
        city, department = parsed_city, parsed_dept

    if not address:
        address = f"{city}, {department}"

    nit = (row.get("nit") or "").strip() or None
    phone = (row.get("phone") or "").strip() or None
    place_id = _make_id(kind, city, name, address, nit)
    return {
        "id": place_id,
        "name": name,
        "address": address,
        "city": city,
        "department": department,
        "kind": kind,
        "lat": None,
        "lng": None,
        "is_partner": False,
        "phone": phone,
        "status": "active",
        "source": "runt",
        "source_updated_at": scraped_at,
        "geocode_confidence": None,
        "geocode_provider": None,
        "geocode_status": "skipped",
        "runt_actor_id": nit,
        "nit": nit,
    }


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--raw-dir", type=Path, default=RAW_DIR)
    parser.add_argument("--out", type=Path, default=OUT_JSON)
    args = parser.parse_args()

    shards = sorted(args.raw_dir.glob("*.json"))
    shards = [p for p in shards if p.name != "scrape_progress.json"]
    places_by_id: dict[str, dict] = {}
    by_kind: Counter[str] = Counter()
    by_dept: Counter[str] = Counter()
    shard_count = 0
    raw_rows = 0

    for shard in shards:
        payload = json.loads(shard.read_text(encoding="utf-8"))
        target = payload.get("target") or {}
        scraped_at = payload.get("scraped_at") or datetime.now(timezone.utc).isoformat()
        rows = payload.get("rows") or []
        shard_count += 1
        raw_rows += len(rows)
        for row in rows:
            place = normalize_row(row, target, scraped_at)
            if place is None:
                continue
            places_by_id[place["id"]] = place

    places = sorted(places_by_id.values(), key=lambda p: (p["kind"], p["department"], p["city"], p["name"]))
    for place in places:
        by_kind[place["kind"]] += 1
        by_dept[place["department"]] += 1

    by_city_kind: dict[str, Counter[str]] = defaultdict(Counter)
    for place in places:
        by_city_kind[place["city"]][place["kind"]] += 1

    summary = {
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "phase": "1_sin_coordenadas",
        "google_geocoding_used": False,
        "shards": shard_count,
        "raw_rows": raw_rows,
        "unique_places": len(places),
        "by_kind": dict(by_kind),
        "by_department": dict(sorted(by_dept.items(), key=lambda item: -item[1])),
        "top_cities": {
            city: dict(counts)
            for city, counts in sorted(by_city_kind.items(), key=lambda item: -sum(item[1].values()))[:30]
        },
        "output": str(args.out),
        "notes": [
            "lat/lng are null until Fase 2 geocoding",
            "large cities may be capped at first RUNT page (~25) if pager did not advance",
        ],
    }

    args.out.parent.mkdir(parents=True, exist_ok=True)
    args.out.write_text(json.dumps(places, ensure_ascii=False, indent=2), encoding="utf-8")
    OUT_SUMMARY.write_text(json.dumps(summary, ensure_ascii=False, indent=2), encoding="utf-8")
    print(json.dumps(summary, ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
