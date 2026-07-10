from __future__ import annotations

import hashlib
import json
import re
from dataclasses import asdict
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from places_service.domain.models import (
    Contact,
    DuplicateCandidate,
    Entity,
    ImportRun,
    Site,
    SourceRecord,
)
from places_service.pipeline.normalize import (
    infer_operational_status,
    normalize_address,
    normalize_document,
    normalize_phone,
    normalize_text,
    resolve_territory,
    strip_accents,
)


def _utc_now() -> str:
    return datetime.now(timezone.utc).isoformat()


def _sha256_file(path: Path) -> str:
    h = hashlib.sha256()
    with path.open("rb") as fh:
        for chunk in iter(lambda: fh.read(1024 * 1024), b""):
            h.update(chunk)
    return h.hexdigest()


def _sha256_text(value: str) -> str:
    return hashlib.sha256(value.encode("utf-8")).hexdigest()


def _stable_id(*parts: str, prefix: str, length: int = 12) -> str:
    digest = hashlib.sha1("|".join(parts).encode("utf-8")).hexdigest()[:length]
    slug = re.sub(r"[^a-z0-9]+", "-", strip_accents(parts[-1] if parts else "x").lower()).strip("-")[:24]
    return f"{prefix}-{slug}-{digest}"[:128]


def _entity_id(doc: dict, legal_name: str) -> tuple[str, bool]:
    # Stable identity by normalized document whenever a number exists.
    # Do not require document_valid — otherwise the same NIT/CC can spawn
    # multiple provisional entities keyed only by name.
    if doc.get("document_number"):
        dtype = str(doc.get("document_type") or "UNKNOWN").lower()
        return (f"ent-{dtype}-{doc['document_number']}"[:128], not bool(doc.get("document_valid")))
    provisional = _stable_id(legal_name or "unknown", prefix="ent-prov")
    return provisional, True


_LEGAL_SUFFIX_RE = re.compile(
    r"\b(S\.?\s*A\.?\s*S\.?|SAS|S\.?\s*A\.?|SA|LTDA\.?|LIMITADA|E\.?\s*U\.?|S\.?\s*C\.?A\.?)\b",
    re.IGNORECASE,
)


def _name_core(name: str) -> str:
    text = normalize_text(name)
    text = _LEGAL_SUFFIX_RE.sub(" ", text)
    text = re.sub(r"[\"“”'`]", " ", text)
    text = re.sub(r"\s*-\s*", " ", text)
    return re.sub(r"\s+", " ", text).strip()


def _site_id(
    actor_type: str,
    entity_id: str,
    municipality_code: str | None,
    municipality_normalized: str,
    address_normalized: str,
    name_normalized: str,
) -> tuple[str, bool]:
    """Stable site identity. Always includes territorial + name cores to avoid silent collisions."""
    muni_key = (municipality_code or municipality_normalized or "na").strip().upper()
    addr = address_normalized or "NO-ADDR"
    name_key = name_normalized or "NO-NAME"
    if municipality_code and address_normalized and "INSUFFICIENT" not in address_normalized:
        return (
            _stable_id(
                actor_type,
                entity_id,
                muni_key,
                addr,
                name_key,
                prefix=f"site-{actor_type.lower()}",
            ),
            False,
        )
    return (
        _stable_id(
            actor_type,
            entity_id,
            muni_key,
            addr,
            name_key,
            prefix=f"site-prov-{actor_type.lower()}",
        ),
        True,
    )


def _disambiguate_site_id(site_id: str, *, row_number: int, source_hash: str) -> str:
    digest = hashlib.sha1(f"{site_id}|{row_number}|{source_hash}".encode("utf-8")).hexdigest()[:10]
    base = site_id[:110].rstrip("-")
    return f"{base}-x{digest}"[:128]


def _quality_score(*, address_quality: str, doc_valid: bool, phone_valid: bool, status: str) -> float:
    score = 0.2
    if address_quality == "valid":
        score += 0.35
    elif address_quality == "partial":
        score += 0.15
    if doc_valid:
        score += 0.2
    if phone_valid:
        score += 0.15
    if status == "unknown":
        score += 0.05
    if status in {"retired", "inactive", "suspended"}:
        score -= 0.2
    return round(max(0.0, min(1.0, score)), 3)


def build_catalog_from_rows(
    rows: list[dict[str, Any]],
    *,
    import_run_id: str,
    source_name: str = "places_colombia_sin_coords",
) -> dict[str, Any]:
    entities: dict[str, Entity] = {}
    sites: dict[str, Site] = {}
    contacts: list[Contact] = []
    source_records: list[SourceRecord] = []
    duplicates_merged: list[dict[str, Any]] = []
    duplicate_candidates: list[DuplicateCandidate] = []
    rejected: list[dict[str, Any]] = []
    review_flags: list[dict[str, Any]] = []
    site_id_collisions: list[dict[str, Any]] = []

    # Exact-dupe key -> site_id
    exact_index: dict[str, str] = {}
    # entity+type -> list of site_ids for multi-sede detection
    entity_sites: dict[str, list[str]] = {}

    for idx, row in enumerate(rows, start=1):
        payload = dict(row)
        source_hash = _sha256_text(json.dumps(payload, ensure_ascii=False, sort_keys=True))
        # Append-only history: include import_run_id so re-imports do not overwrite prior rows.
        source_record_id = f"src-{import_run_id[:8]}-{idx:05d}-{source_hash[:12]}"
        flags: list[str] = []

        kind = str(payload.get("kind") or "").strip().upper()
        if kind not in {"CDA", "CEA", "CIA", "CRC"}:
            rejected.append({"row": idx, "reason": "invalid_actor_type", "payload": payload})
            source_records.append(
                SourceRecord(
                    source_record_id=source_record_id,
                    import_run_id=import_run_id,
                    source_name=source_name,
                    source_row_number=idx,
                    source_payload=payload,
                    source_hash=source_hash,
                    processing_status="rejected_with_reason",
                    processing_flags=["invalid_actor_type"],
                )
            )
            continue

        name = str(payload.get("name") or "").strip()
        if not name:
            rejected.append({"row": idx, "reason": "missing_name", "payload": payload})
            source_records.append(
                SourceRecord(
                    source_record_id=source_record_id,
                    import_run_id=import_run_id,
                    source_name=source_name,
                    source_row_number=idx,
                    source_payload=payload,
                    source_hash=source_hash,
                    processing_status="rejected_with_reason",
                    processing_flags=["missing_name"],
                )
            )
            continue

        doc = normalize_document(payload.get("nit") or payload.get("document") or payload.get("runt_actor_id"))
        # Do NOT copy document into source_actor_id.
        source_actor_id = payload.get("source_actor_id")
        if source_actor_id and str(source_actor_id) == str(payload.get("nit") or ""):
            source_actor_id = None
            flags.append("source_actor_id_was_document_copy")
        if payload.get("runt_actor_id") and str(payload.get("runt_actor_id")) == str(payload.get("nit") or ""):
            flags.append("runt_actor_id_equals_document")

        territory = resolve_territory(payload.get("city"), payload.get("department"))
        address = normalize_address(
            payload.get("address"),
            city=territory["municipality"],
            department=territory["department"],
        )
        phones = normalize_phone(payload.get("phone"))
        status_info = infer_operational_status(name)

        entity_id, entity_review = _entity_id(doc, name)
        if entity_id not in entities:
            entities[entity_id] = Entity(
                entity_id=entity_id,
                document_type=doc["document_type"],
                document_number=doc["document_number"],
                verification_digit=doc["verification_digit"],
                document_raw=doc["document_raw"],
                document_valid=bool(doc["document_valid"]),
                legal_name=name,
                legal_name_normalized=normalize_text(name),
                entity_status="unknown",
                requires_manual_review=entity_review or bool(doc["flags"]),
                created_at=_utc_now(),
                updated_at=_utc_now(),
            )
        else:
            # Prefer longer legal name as display
            if len(name) > len(entities[entity_id].legal_name):
                entities[entity_id].legal_name = name
                entities[entity_id].legal_name_normalized = normalize_text(name)

        site_id, site_provisional = _site_id(
            kind,
            entity_id,
            territory.get("municipality_code"),
            normalize_text(territory["municipality"]),
            address["address_normalized"],
            _name_core(name),
        )

        exact_key = "|".join(
            [
                kind,
                doc.get("document_number") or "",
                _name_core(name),
                address["address_normalized"],
                normalize_text(territory["municipality"]),
                normalize_text(territory["department"]),
            ]
        )

        processing_status = "imported_as_site"
        matched_site_id = site_id

        if exact_key in exact_index:
            existing_site_id = exact_index[exact_key]
            processing_status = "merged_duplicate"
            matched_site_id = existing_site_id
            # Preserve phones from the duplicate row onto the kept site.
            for phone in phones:
                contacts.append(
                    Contact(
                        contact_id=_stable_id(existing_site_id, phone["value_raw"], prefix="ctc"),
                        site_id=existing_site_id,
                        contact_type=phone["contact_type"],
                        value_raw=phone["value_raw"],
                        value_normalized=phone["value_normalized"],
                        e164=phone["e164"],
                        is_valid=phone["is_valid"],
                        is_public=False,
                        source_record_id=source_record_id,
                    )
                )
            duplicates_merged.append(
                {
                    "rule": "exact_normalized_match",
                    "confidence": 1.0,
                    "kept_site_id": existing_site_id,
                    "merged_source_record_id": source_record_id,
                    "row": idx,
                    "phones_merged": len(phones),
                }
            )
            source_records.append(
                SourceRecord(
                    source_record_id=source_record_id,
                    import_run_id=import_run_id,
                    source_name=source_name,
                    source_row_number=idx,
                    source_payload=payload,
                    source_hash=source_hash,
                    matched_entity_id=entity_id,
                    matched_site_id=existing_site_id,
                    processing_status=processing_status,
                    processing_flags=flags + doc["flags"] + address["flags"] + territory["flags"] + ["exact_duplicate"],
                )
            )
            continue

        if site_id in sites:
            # Never overwrite. Disambiguate and keep both sites for review.
            collision_original = site_id
            site_id = _disambiguate_site_id(site_id, row_number=idx, source_hash=source_hash)
            site_provisional = True
            flags.append("site_id_collision_disambiguated")
            flags.append("requires_manual_review")
            site_id_collisions.append(
                {
                    "row_number": idx,
                    "source_record_id": source_record_id,
                    "original_site_id": collision_original,
                    "disambiguated_site_id": site_id,
                    "previous_site_id": collision_original,
                    "name": name,
                    "document_number": doc.get("document_number"),
                    "address_normalized": address["address_normalized"],
                    "municipality": territory["municipality"],
                    "actor_type": kind,
                    "collision_reason": "site_id_hash_collision_without_exact_merge",
                    "proposed_classification": "kept_both_disambiguated",
                }
            )
            matched_site_id = site_id
            processing_status = "pending_review"

        # Same document + different address => multi-sede (keep) but candidate note
        if doc.get("document_number"):
            key = f"{kind}|{doc['document_number']}"
            prior = entity_sites.get(key, [])
            if prior:
                for other_id in prior:
                    other = sites[other_id]
                    if other.address_normalized != address["address_normalized"]:
                        duplicate_candidates.append(
                            DuplicateCandidate(
                                candidate_id=_stable_id(
                                    other_id, site_id, "same_document_different_address", prefix="dup"
                                ),
                                import_run_id=import_run_id,
                                site_id_a=other_id,
                                site_id_b=site_id,
                                confidence=0.4,
                                reason="same_document_different_address",
                                rule="multi_sede_or_possible_duplicate",
                            )
                        )
                        flags.append("same_document_different_address")

        review_doc_flags = {
            "missing_document",
            "ambiguous_document_type",
            "atypical_document_length",
            "invalid_nit_verification_digit",
            "possible_nit_invalid_verification_digit",
            "document_collision",
            "nit_body_length_unusual",
        }
        requires_review = (
            entity_review
            or site_provisional
            or status_info["requires_manual_review"]
            or "insufficient_for_geocoding" in address["flags"]
            or territory["confidence"] == "none"
            or bool(set(doc.get("flags") or []) & review_doc_flags)
            or "site_id_collision_disambiguated" in flags
        )
        if requires_review:
            flags.append("requires_manual_review")
            review_flags.append({"row": idx, "site_id": site_id, "flags": list(flags)})

        phone_valid = any(p["is_valid"] for p in phones)
        geocode_status = "not_attempted"
        if "insufficient_for_geocoding" in address["flags"] or address["address_quality"] in {"missing", "invalid"}:
            geocode_status = "insufficient_address"

        if status_info["exclude_from_normal_search"]:
            processing_status = "pending_review"
            flags.append("excluded_from_normal_search")

        site = Site(
            site_id=site_id,
            entity_id=entity_id,
            actor_type=kind,
            source_actor_id=str(source_actor_id) if source_actor_id else None,
            name=name,
            name_normalized=normalize_text(name),
            address_raw=address["address_raw"],
            address_normalized=address["address_normalized"],
            address_quality=address["address_quality"],
            department=territory["department"],
            department_code=territory.get("department_code"),
            municipality=territory["municipality"],
            municipality_code=territory.get("municipality_code"),
            population_center=territory.get("population_center"),
            locality=territory.get("locality"),
            raw_city=territory["raw_city"],
            raw_department=territory["raw_department"],
            lat=None,
            lng=None,
            geocode_status=geocode_status,
            operational_status=status_info["operational_status"],
            status_verified=status_info["status_verified"],
            status_source=status_info["status_source"],
            status_inferred_from_name=status_info["status_inferred_from_name"],
            is_official_actor=True,
            is_partner=False,
            is_bookable=False,
            booking_mode="information_only",
            quality_score=_quality_score(
                address_quality=address["address_quality"],
                doc_valid=bool(doc["document_valid"]),
                phone_valid=phone_valid,
                status=status_info["operational_status"],
            ),
            requires_manual_review=requires_review,
            snapshot_presence="present",
            last_seen_import_run_id=import_run_id,
            created_at=_utc_now(),
            updated_at=_utc_now(),
        )
        if site_id in sites:
            raise RuntimeError(f"refusing silent site_id overwrite: {site_id}")
        sites[site_id] = site
        exact_index[exact_key] = site_id
        entity_sites.setdefault(f"{kind}|{doc.get('document_number') or entity_id}", []).append(site_id)

        for phone in phones:
            contacts.append(
                Contact(
                    contact_id=_stable_id(site_id, phone["value_raw"], prefix="ctc"),
                    site_id=site_id,
                    contact_type=phone["contact_type"],
                    value_raw=phone["value_raw"],
                    value_normalized=phone["value_normalized"],
                    e164=phone["e164"],
                    is_valid=phone["is_valid"],
                    is_public=False,
                    source_record_id=source_record_id,
                )
            )

        source_records.append(
            SourceRecord(
                source_record_id=source_record_id,
                import_run_id=import_run_id,
                source_name=source_name,
                source_row_number=idx,
                source_payload=payload,
                source_hash=source_hash,
                matched_entity_id=entity_id,
                matched_site_id=matched_site_id,
                processing_status=processing_status,
                processing_flags=flags + doc["flags"] + address["flags"] + territory["flags"],
            )
        )

    # Reconcile counts
    status_counts: dict[str, int] = {}
    for rec in source_records:
        status_counts[rec.processing_status] = status_counts.get(rec.processing_status, 0) + 1

    return {
        "entities": list(entities.values()),
        "sites": list(sites.values()),
        "contacts": contacts,
        "source_records": source_records,
        "duplicates_merged": duplicates_merged,
        "duplicate_candidates": duplicate_candidates,
        "rejected": rejected,
        "review_flags": review_flags,
        "site_id_collisions": site_id_collisions,
        "reconciliation": {
            "input_rows": len(rows),
            "source_records": len(source_records),
            "by_processing_status": status_counts,
            "unique_entities": len(entities),
            "unique_sites": len(sites),
            "merged_duplicates": len(duplicates_merged),
            "duplicate_candidates": len(duplicate_candidates),
            "site_id_collisions_disambiguated": len(site_id_collisions),
            "rejected": len(rejected),
            "sum_check": sum(status_counts.values()),
            "sum_matches_input": sum(status_counts.values()) == len(rows),
            "non_merged_equals_unique_sites": (
                status_counts.get("imported_as_site", 0) + status_counts.get("pending_review", 0)
            )
            == len(sites),
        },
    }


def write_reports(catalog: dict[str, Any], report_dir: Path, *, import_run: ImportRun) -> None:
    report_dir.mkdir(parents=True, exist_ok=True)
    processed_dir = report_dir.parent / "processed"
    processed_dir.mkdir(parents=True, exist_ok=True)

    def dump(name: str, payload: Any) -> None:
        path = report_dir / name
        path.write_text(json.dumps(payload, ensure_ascii=False, indent=2, default=asdict_default), encoding="utf-8")

    sites = catalog["sites"]
    entities = catalog["entities"]
    contacts = catalog["contacts"]
    source_records = catalog["source_records"]

    processed_dir.joinpath("places_catalog.json").write_text(
        json.dumps([asdict(s) for s in sites], ensure_ascii=False, indent=2),
        encoding="utf-8",
    )
    processed_dir.joinpath("entities.json").write_text(
        json.dumps([asdict(e) for e in entities], ensure_ascii=False, indent=2),
        encoding="utf-8",
    )

    by_type: dict[str, int] = {}
    by_status: dict[str, int] = {}
    for site in sites:
        by_type[site.actor_type] = by_type.get(site.actor_type, 0) + 1
        by_status[site.operational_status] = by_status.get(site.operational_status, 0) + 1

    metrics = {
        "import_run_id": import_run.import_run_id,
        "input_sha256": import_run.input_sha256,
        "source_records": len(source_records),
        "unique_entities": len(entities),
        "unique_sites": len(sites),
        "by_actor_type": by_type,
        "by_operational_status": by_status,
        "partners": sum(1 for s in sites if s.is_partner),
        "bookable": sum(1 for s in sites if s.is_bookable),
        "geocoded": sum(1 for s in sites if s.lat is not None and s.lng is not None),
        "pending_geocoding": sum(1 for s in sites if s.geocode_status in {"not_attempted", "pending"}),
        "insufficient_address": sum(1 for s in sites if s.geocode_status == "insufficient_address"),
        "manual_review": sum(1 for s in sites if s.requires_manual_review),
        "duplicate_candidates": len(catalog["duplicate_candidates"]),
        "merged_duplicates": len(catalog["duplicates_merged"]),
        "invalid_addresses": sum(1 for s in sites if s.address_quality in {"invalid", "missing"}),
        "partial_addresses": sum(1 for s in sites if s.address_quality == "partial"),
        "valid_addresses": sum(1 for s in sites if s.address_quality == "valid"),
        "valid_phones": sum(1 for c in contacts if c.is_valid),
        "invalid_phones": sum(1 for c in contacts if not c.is_valid),
        "valid_documents": sum(1 for e in entities if e.document_valid),
        "invalid_documents": sum(1 for e in entities if not e.document_valid),
        "reconciliation": catalog["reconciliation"],
        "source_updated_at": import_run.source_updated_at,
        "snapshot_at": import_run.snapshot_at,
    }
    dump("data_quality_metrics.json", metrics)
    dump("reconciliation.json", catalog["reconciliation"])
    dump("merged_duplicates.json", catalog["duplicates_merged"])
    dump("duplicate_candidates.json", [asdict(c) for c in catalog["duplicate_candidates"]])
    dump("rejected_records.json", catalog["rejected"])
    dump("site_id_collisions.json", catalog.get("site_id_collisions") or [])
    dump(
        "document_review.json",
        [
            asdict(e)
            for e in entities
            if e.requires_manual_review or not e.document_valid
        ],
    )
    dump(
        "territorial_review.json",
        [
            {
                "site_id": s.site_id,
                "raw_city": s.raw_city,
                "raw_department": s.raw_department,
                "municipality": s.municipality,
                "department": s.department,
                "municipality_code": s.municipality_code,
            }
            for s in sites
            if not s.municipality_code
        ],
    )
    dump(
        "address_review.json",
        [
            {
                "site_id": s.site_id,
                "address_raw": s.address_raw,
                "address_quality": s.address_quality,
            }
            for s in sites
            if s.address_quality != "valid"
        ],
    )
    dump(
        "phone_review.json",
        [asdict(c) for c in contacts if not c.is_valid],
    )
    dump(
        "geocoding_report.json",
        {
            "mode": "disabled",
            "total_sites": len(sites),
            "geocoded": 0,
            "not_attempted": sum(1 for s in sites if s.geocode_status == "not_attempted"),
            "insufficient_address": sum(1 for s in sites if s.geocode_status == "insufficient_address"),
            "note": "Geocoding disabled by default; no external calls made.",
        },
    )


def asdict_default(obj: Any) -> Any:
    if hasattr(obj, "__dataclass_fields__"):
        return asdict(obj)
    raise TypeError(type(obj))
