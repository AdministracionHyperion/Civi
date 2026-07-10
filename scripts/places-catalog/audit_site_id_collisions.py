"""Audit silent site_id collisions in the current catalog builder logic."""

from __future__ import annotations

import hashlib
import json
from pathlib import Path

from places_service.pipeline.catalog_builder import _entity_id, _sha256_text, _site_id
from places_service.pipeline.normalize import normalize_address, normalize_document, normalize_text, resolve_territory

ROOT = Path(__file__).resolve().parents[2]
RAW = ROOT / "services" / "places-service" / "data" / "raw" / "places_colombia_original.json"
OUT = ROOT / "services" / "places-service" / "data" / "reports" / "site_id_collisions_before_fix.json"


def main() -> None:
    rows = json.loads(RAW.read_text(encoding="utf-8"))
    assert len(rows) == 4107
    sha = hashlib.sha256(RAW.read_bytes()).hexdigest()
    counts = {k: sum(1 for r in rows if str(r.get("kind") or "").upper() == k) for k in ("CDA", "CEA", "CIA", "CRC")}
    print("sha", sha)
    print("counts", counts)

    sites: dict[str, dict] = {}
    exact_index: dict[str, str] = {}
    collisions: list[dict] = []

    for idx, row in enumerate(rows, 1):
        payload = dict(row)
        source_hash = _sha256_text(json.dumps(payload, ensure_ascii=False, sort_keys=True))
        source_record_id = f"src-{idx:05d}-{source_hash[:16]}"
        kind = str(payload.get("kind") or "").strip().upper()
        if kind not in {"CDA", "CEA", "CIA", "CRC"}:
            continue
        name = str(payload.get("name") or "").strip()
        if not name:
            continue
        doc = normalize_document(payload.get("nit") or payload.get("document") or payload.get("runt_actor_id"))
        territory = resolve_territory(payload.get("city"), payload.get("department"))
        address = normalize_address(
            payload.get("address"),
            city=territory["municipality"],
            department=territory["department"],
        )
        entity_id, _ = _entity_id(doc, name)
        site_id, provisional = _site_id(
            kind,
            entity_id,
            territory.get("municipality_code"),
            address["address_normalized"],
            name,
        )
        exact_key = "|".join(
            [
                kind,
                doc.get("document_number") or "",
                normalize_text(name),
                address["address_normalized"],
                territory["municipality"],
                territory["department"],
            ]
        )
        if exact_key in exact_index:
            continue
        if site_id in sites:
            prev = sites[site_id]
            collisions.append(
                {
                    "row_number": idx,
                    "source_record_id": source_record_id,
                    "site_id": site_id,
                    "site_provisional": provisional,
                    "actor_type": kind,
                    "name": name,
                    "document_raw": doc.get("document_raw"),
                    "document_number": doc.get("document_number"),
                    "document_type": doc.get("document_type"),
                    "address_raw": address["address_raw"],
                    "address_normalized": address["address_normalized"],
                    "municipality": territory["municipality"],
                    "department": territory["department"],
                    "municipality_code": territory.get("municipality_code"),
                    "previous": {
                        "name": prev["name"],
                        "document_number": prev["document_number"],
                        "document_raw": prev["document_raw"],
                        "address_raw": prev["address_raw"],
                        "address_normalized": prev["address_normalized"],
                        "municipality": prev["municipality"],
                        "department": prev["department"],
                        "actor_type": prev["actor_type"],
                        "row_number": prev["row_number"],
                        "source_record_id": prev["source_record_id"],
                        "exact_key": prev["exact_key"],
                    },
                    "current_exact_key": exact_key,
                    "collision_reason": "site_id_overwrite_without_exact_merge",
                    "proposed_classification": (
                        "distinct_sites_same_hash_key"
                        if prev["exact_key"] != exact_key
                        else "should_have_been_exact_merge"
                    ),
                }
            )
        sites[site_id] = {
            "name": name,
            "document_number": doc.get("document_number"),
            "document_raw": doc.get("document_raw"),
            "address_raw": address["address_raw"],
            "address_normalized": address["address_normalized"],
            "municipality": territory["municipality"],
            "department": territory["department"],
            "actor_type": kind,
            "row_number": idx,
            "source_record_id": source_record_id,
            "exact_key": exact_key,
        }
        exact_index[exact_key] = site_id

    report = {
        "input_sha256": sha,
        "input_rows": len(rows),
        "collision_count": len(collisions),
        "unique_sites_after_overwrite": len(sites),
        "non_merged_expected": None,
        "collisions": collisions,
    }
    OUT.parent.mkdir(parents=True, exist_ok=True)
    OUT.write_text(json.dumps(report, ensure_ascii=False, indent=2), encoding="utf-8")
    print("unique_sites", len(sites))
    print("collisions", len(collisions))
    print("wrote", OUT)
    for c in collisions:
        print("---")
        print(c["row_number"], c["site_id"], c["name"][:80])
        print(" prev", c["previous"]["row_number"], c["previous"]["name"][:80])
        print(" addr cur", c["address_normalized"][:100])
        print(" addr prv", c["previous"]["address_normalized"][:100])
        print(" muni", c["municipality"], c.get("municipality_code"), "|", c["previous"]["municipality"])
        print(" class", c["proposed_classification"])


if __name__ == "__main__":
    main()
