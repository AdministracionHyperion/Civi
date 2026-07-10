from __future__ import annotations

import json
import hashlib
import math
import os
from dataclasses import asdict
from datetime import datetime, timezone
from typing import Any
from uuid import uuid4

from sqlalchemy import and_, case, func, or_, select
from sqlalchemy.dialects.postgresql import insert as pg_insert
from sqlalchemy.dialects.sqlite import insert as sqlite_insert
from sqlalchemy.engine import Engine

from civi_common.geo import is_colombia_latlng
from places_service.adapters.outbound.schema import (
    create_engine_from_url,
    places,
    places_contacts,
    places_duplicate_candidates,
    places_entities,
    places_import_source_records,
    places_import_runs,
    places_presence_events,
    places_sites,
    places_source_records,
)
from places_service.domain.models import Contact, Entity, ImportRun, Site
from places_service.shared.catalog import PLACES, Place


EXCLUDED_STATUSES = frozenset({"retired", "inactive", "suspended"})


class CatalogSqlRepository:
    def __init__(self, database_url: str, *, create_schema: bool = False) -> None:
        self.engine: Engine = create_engine_from_url(database_url)
        if create_schema:
            from places_service.adapters.outbound.migrate import migrate_schema

            migrate_schema(self.engine)

    def apply_import(
        self,
        *,
        import_run: ImportRun,
        entities: list[Entity],
        sites: list[Site],
        contacts: list[Contact],
        source_records: list[Any],
        duplicate_candidates: list[Any],
        preserve_partner_flags: bool = True,
    ) -> dict[str, int]:
        now = import_run.completed_at or datetime.now(timezone.utc).isoformat()
        counts = {"inserted": 0, "updated": 0, "unchanged": 0, "entities_inserted": 0,
                  "entities_updated": 0, "missing": 0, "reappeared": 0}
        present_ids = {site.site_id for site in sites}
        try:
            with self.engine.begin() as conn:
                run_payload = _import_run_payload(import_run, status="running", completed_at=None)
                conn.execute(_upsert(self.engine, places_import_runs, run_payload, pk="import_run_id"))

                for entity in entities:
                    payload = asdict(entity)
                    payload["content_hash"] = _content_hash(payload)
                    payload["created_at"] = payload["created_at"] or now
                    payload["updated_at"] = payload["updated_at"] or now
                    current = conn.execute(
                        select(places_entities).where(places_entities.c.entity_id == entity.entity_id)
                    ).mappings().first()
                    if current is None:
                        conn.execute(places_entities.insert().values(**payload))
                        counts["entities_inserted"] += 1
                    elif current.get("content_hash") != payload["content_hash"]:
                        payload["created_at"] = current["created_at"]
                        conn.execute(
                            places_entities.update()
                            .where(places_entities.c.entity_id == entity.entity_id)
                            .values(**{key: value for key, value in payload.items() if key != "entity_id"})
                        )
                        counts["entities_updated"] += 1

                for site in sites:
                    payload = asdict(site)
                    current = conn.execute(
                        select(places_sites).where(places_sites.c.site_id == site.site_id)
                    ).mappings().first()
                    if preserve_partner_flags and current and (current["is_partner"] or current["is_bookable"]):
                        payload.update(
                            is_partner=bool(current["is_partner"]),
                            is_bookable=bool(current["is_bookable"]),
                            booking_mode=str(current["booking_mode"]),
                        )
                    if payload["operational_status"] in EXCLUDED_STATUSES:
                        payload["is_bookable"] = False
                        payload["booking_mode"] = "unavailable"
                    payload["content_hash"] = _content_hash(payload)
                    payload.update(
                        snapshot_presence="present",
                        source_presence_status="present",
                        present_in_latest_snapshot=True,
                        last_seen_import_run_id=import_run.import_run_id,
                        last_seen_import_run=import_run.import_run_id,
                        missing_since_import_run=None,
                        last_seen_at=now,
                    )
                    if current is None:
                        payload.update(
                            first_seen_import_run=import_run.import_run_id,
                            first_seen_at=now,
                            created_at=payload["created_at"] or now,
                            updated_at=payload["updated_at"] or now,
                        )
                        conn.execute(places_sites.insert().values(**payload))
                        _insert_presence_event(
                            conn,
                            site_id=site.site_id,
                            import_run_id=import_run.import_run_id,
                            previous_status=None,
                            new_status="present",
                            event_type="first_seen",
                            reason="inserted_from_snapshot",
                            created_at=now,
                        )
                        counts["inserted"] += 1
                        changed = True
                    elif current.get("content_hash") == payload["content_hash"]:
                        lifecycle = {
                            key: payload[key]
                            for key in (
                                "snapshot_presence", "source_presence_status", "present_in_latest_snapshot",
                                "last_seen_import_run_id", "last_seen_import_run", "missing_since_import_run",
                                "last_seen_at",
                            )
                        }
                        if current.get("source_presence_status") == "missing":
                            lifecycle["source_presence_status"] = "reappeared"
                            counts["reappeared"] += 1
                            _insert_presence_event(
                                conn,
                                site_id=site.site_id,
                                import_run_id=import_run.import_run_id,
                                previous_status="missing",
                                new_status="reappeared",
                                event_type="reappeared",
                                reason="returned_in_snapshot",
                                created_at=now,
                            )
                        conn.execute(
                            places_sites.update().where(places_sites.c.site_id == site.site_id).values(**lifecycle)
                        )
                        counts["unchanged"] += 1
                        changed = False
                    else:
                        if current.get("source_presence_status") == "missing":
                            payload["source_presence_status"] = "reappeared"
                            counts["reappeared"] += 1
                            _insert_presence_event(
                                conn,
                                site_id=site.site_id,
                                import_run_id=import_run.import_run_id,
                                previous_status="missing",
                                new_status="reappeared",
                                event_type="reappeared",
                                reason="returned_in_snapshot",
                                created_at=now,
                            )
                        payload["created_at"] = current["created_at"]
                        payload["first_seen_import_run"] = current["first_seen_import_run"]
                        payload["first_seen_at"] = current["first_seen_at"]
                        payload["updated_at"] = now
                        conn.execute(
                            places_sites.update()
                            .where(places_sites.c.site_id == site.site_id)
                            .values(**{key: value for key, value in payload.items() if key != "site_id"})
                        )
                        counts["updated"] += 1
                        changed = True
                    if changed:
                        conn.execute(_upsert(self.engine, places, _legacy_site_payload(site, payload, import_run), pk="id"))

                for row in conn.execute(select(places_sites)).mappings():
                    if row["site_id"] in present_ids:
                        continue
                    if row.get("source_presence_status") == "missing":
                        continue
                    previous_status = str(row.get("source_presence_status") or "present")
                    conn.execute(
                        places_sites.update()
                        .where(places_sites.c.site_id == row["site_id"])
                        .values(
                            snapshot_presence="absent",
                            source_presence_status="missing",
                            present_in_latest_snapshot=False,
                            missing_since_import_run=import_run.import_run_id,
                            is_bookable=False,
                            booking_mode="unavailable",
                            updated_at=now,
                        )
                    )
                    _insert_presence_event(
                        conn,
                        site_id=row["site_id"],
                        import_run_id=import_run.import_run_id,
                        previous_status=previous_status,
                        new_status="missing",
                        event_type="missing",
                        reason="absent_from_snapshot",
                        created_at=now,
                    )
                    counts["missing"] += 1

                for contact in contacts:
                    conn.execute(_upsert(self.engine, places_contacts, asdict(contact), pk="contact_id"))
                for rec in source_records:
                    payload = asdict(rec)
                    legacy_payload = {
                        **payload,
                        "source_payload": json.dumps(payload["source_payload"], ensure_ascii=False, sort_keys=True),
                        "processing_flags": json.dumps(payload["processing_flags"], ensure_ascii=False),
                    }
                    legacy_payload.pop("observed_at")
                    conn.execute(_upsert(self.engine, places_source_records, legacy_payload, pk="source_record_id"))
                    conn.execute(
                        places_import_source_records.insert().values(
                            import_run_id=import_run.import_run_id,
                            source_record_id=payload["source_record_id"],
                            source_row_number=payload["source_row_number"],
                            source_hash=payload["source_hash"],
                            observed_payload=json.dumps(payload["source_payload"], ensure_ascii=False, sort_keys=True),
                            processing_status=payload["processing_status"],
                            processing_flags=json.dumps(payload["processing_flags"], ensure_ascii=False),
                            matched_entity_id=payload["matched_entity_id"],
                            matched_site_id=payload["matched_site_id"],
                            observed_at=payload["observed_at"] or now,
                        )
                    )
                for cand in duplicate_candidates:
                    conn.execute(_upsert(self.engine, places_duplicate_candidates, asdict(cand), pk="candidate_id"))

                final_payload = _import_run_payload(
                    import_run, status="applied", completed_at=now, counts=counts
                )
                conn.execute(_upsert(self.engine, places_import_runs, final_payload, pk="import_run_id"))
        except Exception as exc:
            with self.engine.begin() as conn:
                failed = _import_run_payload(
                    import_run,
                    status="failed",
                    completed_at=None,
                    counts=counts,
                    error_code=type(exc).__name__,
                    error_message=str(exc),
                    failed_at=datetime.now(timezone.utc).isoformat(),
                )
                conn.execute(_upsert(self.engine, places_import_runs, failed, pk="import_run_id"))
            raise
        return {**counts, "absent_marked": counts["missing"]}

    def get_site(self, site_id: str) -> dict[str, Any] | None:
        with self.engine.begin() as conn:
            row = conn.execute(select(places_sites).where(places_sites.c.site_id == site_id)).mappings().first()
        return dict(row) if row else None

    def get_ops_contact(self, site_id: str) -> dict[str, Any] | None:
        with self.engine.begin() as conn:
            row = (
                conn.execute(
                    select(
                        places_sites.c.site_id,
                        places_sites.c.name,
                        places_contacts.c.e164,
                    )
                    .select_from(
                        places_sites.join(
                            places_contacts,
                            places_contacts.c.site_id == places_sites.c.site_id,
                        )
                    )
                    .where(places_sites.c.site_id == site_id)
                    .where(places_contacts.c.contact_type == "ops_whatsapp")
                    .where(places_contacts.c.e164.is_not(None))
                    .where(places_contacts.c.e164 != "")
                    .where(places_contacts.c.is_valid == True)  # noqa: E712
                    .limit(1)
                )
                .mappings()
                .first()
            )
        if row is None:
            return None
        return {
            "site_id": str(row["site_id"]),
            "name": str(row["name"]),
            "e164": _normalize_e164(str(row["e164"])),
        }

    def lookup_by_ops_whatsapp(self, e164: str) -> dict[str, Any] | None:
        needle = _normalize_e164(e164)
        if not needle:
            return None
        with self.engine.begin() as conn:
            rows = (
                conn.execute(
                    select(
                        places_sites.c.site_id,
                        places_sites.c.name,
                        places_contacts.c.e164,
                    )
                    .select_from(
                        places_sites.join(
                            places_contacts,
                            places_contacts.c.site_id == places_sites.c.site_id,
                        )
                    )
                    .where(places_contacts.c.contact_type == "ops_whatsapp")
                    .where(places_contacts.c.is_valid == True)  # noqa: E712
                    .where(places_contacts.c.e164.is_not(None))
                    .where(places_contacts.c.e164 != "")
                )
                .mappings()
                .all()
            )
        for row in rows:
            if _normalize_e164(str(row["e164"])) == needle:
                return {
                    "site_id": str(row["site_id"]),
                    "name": str(row["name"]),
                    "e164": needle,
                }
        return None

    def set_partner(self, *, site_id: str, ops_whatsapp: str) -> dict[str, Any]:
        e164 = _normalize_e164(ops_whatsapp)
        if len(e164) < 10:
            raise ValueError("ops_whatsapp must be a valid E.164 phone (digits only, min 10)")
        now = datetime.now(timezone.utc).isoformat()
        with self.engine.begin() as conn:
            site = (
                conn.execute(select(places_sites).where(places_sites.c.site_id == site_id))
                .mappings()
                .first()
            )
            if site is None:
                raise LookupError(f"site not found: {site_id}")
            conn.execute(
                places_sites.update()
                .where(places_sites.c.site_id == site_id)
                .values(
                    is_partner=True,
                    is_bookable=True,
                    booking_mode="civi",
                    updated_at=now,
                )
            )
            existing = (
                conn.execute(
                    select(places_contacts)
                    .where(places_contacts.c.site_id == site_id)
                    .where(places_contacts.c.contact_type == "ops_whatsapp")
                    .limit(1)
                )
                .mappings()
                .first()
            )
            contact_id = str(existing["contact_id"]) if existing else f"ops-{site_id}"
            payload = {
                "contact_id": contact_id,
                "site_id": site_id,
                "contact_type": "ops_whatsapp",
                "value_raw": ops_whatsapp.strip(),
                "value_normalized": e164,
                "e164": e164,
                "is_valid": True,
                "is_public": False,
                "source_record_id": None,
            }
            conn.execute(_upsert(self.engine, places_contacts, payload, pk="contact_id"))
        return {
            "site_id": site_id,
            "is_partner": True,
            "is_bookable": True,
            "booking_mode": "civi",
            "ops_whatsapp": e164,
            "name": str(site["name"]),
        }

    def booking_eligibility(self, site_id: str) -> dict[str, Any]:
        site = self.get_site(site_id)
        if site is None:
            return {
                "site_id": site_id,
                "exists": False,
                "is_partner": False,
                "is_bookable": False,
                "eligible_for_civi_booking": False,
                "eligibility_reason": "site_not_found",
                "booking_mode": "unavailable",
                "operational_status": "unknown",
                "source_presence_status": "missing",
                "present_in_latest_snapshot": False,
                "canonical_name": None,
                "canonical_address": None,
                "canonical_city": None,
            }
        status = str(site.get("operational_status") or "unknown")
        presence = str(site.get("source_presence_status") or "unknown")
        is_partner = bool(site["is_partner"])
        booking_mode = str(site.get("booking_mode") or "information_only")
        is_bookable = bool(site["is_bookable"])
        ops = self.get_ops_contact(site_id)
        eligible = False
        reason = "not_civi_partner"
        if status in EXCLUDED_STATUSES:
            is_bookable = False
            booking_mode = "unavailable"
            reason = f"operational_status_{status}"
        elif presence not in {"present", "reappeared", "manually_preserved"}:
            is_bookable = False
            booking_mode = "unavailable"
            reason = "missing_from_latest_snapshot"
        elif not is_partner or booking_mode != "civi":
            is_bookable = False
            reason = "not_civi_partner"
        elif not is_bookable:
            reason = "not_bookable"
        elif ops is None:
            is_bookable = False
            reason = "missing_ops_whatsapp"
        else:
            eligible = True
            reason = "eligible"
        return {
            "site_id": site_id,
            "exists": True,
            "is_partner": is_partner,
            "is_bookable": is_bookable,
            "eligible_for_civi_booking": eligible,
            "eligibility_reason": reason,
            "booking_mode": booking_mode,
            "operational_status": status,
            "snapshot_presence": site.get("snapshot_presence"),
            "source_presence_status": presence,
            "present_in_latest_snapshot": bool(site.get("present_in_latest_snapshot")),
            "canonical_name": site["name"],
            "canonical_address": site["address_raw"],
            "canonical_city": site["municipality"],
        }

    def catalog_summary(self) -> dict[str, Any]:
        with self.engine.begin() as conn:
            entities = conn.execute(select(func.count()).select_from(places_entities)).scalar_one()
            valid_documents = conn.execute(
                select(func.count())
                .select_from(places_entities)
                .where(places_entities.c.document_valid == True)  # noqa: E712
            ).scalar_one()
            invalid_documents = conn.execute(
                select(func.count())
                .select_from(places_entities)
                .where(places_entities.c.document_valid == False)  # noqa: E712
            ).scalar_one()
            candidate_documents = conn.execute(
                select(func.count())
                .select_from(places_entities)
                .where(places_entities.c.document_validation_status == "candidate_without_dv")
            ).scalar_one()
            ambiguous_documents = conn.execute(
                select(func.count())
                .select_from(places_entities)
                .where(places_entities.c.document_validation_status == "ambiguous")
            ).scalar_one()
            missing_documents = conn.execute(
                select(func.count())
                .select_from(places_entities)
                .where(places_entities.c.document_validation_status == "missing")
            ).scalar_one()
            by_document_validation = {
                str(value): int(count)
                for value, count in conn.execute(
                    select(places_entities.c.document_validation_status, func.count())
                    .select_from(places_entities)
                    .group_by(places_entities.c.document_validation_status)
                ).all()
                if value is not None
            }
            source_records = conn.execute(select(func.count()).select_from(places_source_records)).scalar_one()
            dupes = conn.execute(select(func.count()).select_from(places_duplicate_candidates)).scalar_one()
            invalid_phones = conn.execute(
                select(func.count())
                .select_from(places_contacts)
                .where(places_contacts.c.is_valid == False)  # noqa: E712
            ).scalar_one()
            latest = conn.execute(
                select(places_import_runs).order_by(places_import_runs.c.started_at.desc()).limit(1)
            ).mappings().first()
            site_counts = conn.execute(
                select(
                    func.count().label("unique_sites"),
                    func.coalesce(func.sum(_bool_as_int(places_sites.c.is_partner)), 0).label("partners"),
                    func.coalesce(func.sum(_bool_as_int(places_sites.c.is_bookable)), 0).label("bookable"),
                    func.coalesce(
                        func.sum(
                            _bool_as_int(
                                and_(
                                    places_sites.c.lat.is_not(None),
                                    places_sites.c.lng.is_not(None),
                                )
                            )
                        ),
                        0,
                    ).label("geocoded"),
                    func.coalesce(
                        func.sum(
                            _bool_as_int(places_sites.c.geocode_status.in_(("not_attempted", "pending")))
                        ),
                        0,
                    ).label("pending_geocoding"),
                    func.coalesce(
                        func.sum(_bool_as_int(places_sites.c.geocode_status == "low_confidence")),
                        0,
                    ).label("low_confidence_geocodes"),
                    func.coalesce(
                        func.sum(_bool_as_int(places_sites.c.requires_manual_review)),
                        0,
                    ).label("manual_review"),
                    func.coalesce(
                        func.sum(
                            _bool_as_int(places_sites.c.address_quality.in_(("invalid", "missing")))
                        ),
                        0,
                    ).label("invalid_addresses"),
                    func.coalesce(
                        func.sum(
                            _bool_as_int(
                                or_(
                                    places_sites.c.snapshot_presence == "absent",
                                    places_sites.c.source_presence_status == "missing",
                                )
                            )
                        ),
                        0,
                    ).label("absent_from_snapshot"),
                    func.coalesce(
                        func.sum(
                            _bool_as_int(
                                places_sites.c.source_presence_status.in_(
                                    ("present", "reappeared", "manually_preserved")
                                )
                            )
                        ),
                        0,
                    ).label("present_sites"),
                    func.coalesce(
                        func.sum(_bool_as_int(places_sites.c.source_presence_status == "reappeared")),
                        0,
                    ).label("reappeared_sites"),
                ).select_from(places_sites)
            ).mappings().one()
            by_type = _grouped_counts(conn, places_sites.c.actor_type)
            by_status = _grouped_counts(conn, places_sites.c.operational_status)
            by_presence = _grouped_counts(conn, places_sites.c.source_presence_status)
            by_geocode = _grouped_counts(conn, places_sites.c.geocode_status)
        return {
            "source_records": int(source_records or 0),
            "unique_entities": int(entities or 0),
            "unique_sites": int(site_counts["unique_sites"] or 0),
            "by_actor_type": by_type,
            "by_operational_status": by_status,
            "by_source_presence_status": by_presence,
            "by_geocode_status": by_geocode,
            "by_document_validation_status": by_document_validation,
            "partners": int(site_counts["partners"] or 0),
            "bookable": int(site_counts["bookable"] or 0),
            "geocoded": int(site_counts["geocoded"] or 0),
            "pending_geocoding": int(site_counts["pending_geocoding"] or 0),
            "low_confidence_geocodes": int(site_counts["low_confidence_geocodes"] or 0),
            "manual_review": int(site_counts["manual_review"] or 0),
            "duplicate_candidates": int(dupes or 0),
            "invalid_addresses": int(site_counts["invalid_addresses"] or 0),
            "invalid_phones": int(invalid_phones or 0),
            "valid_documents": int(valid_documents or 0),
            "invalid_documents": int(invalid_documents or 0),
            "candidate_documents": int(candidate_documents or 0),
            "ambiguous_documents": int(ambiguous_documents or 0),
            "missing_documents": int(missing_documents or 0),
            "absent_from_snapshot": int(site_counts["absent_from_snapshot"] or 0),
            "missing": int(site_counts["absent_from_snapshot"] or 0),
            "present_sites": int(site_counts["present_sites"] or 0),
            "reappeared_sites": int(site_counts["reappeared_sites"] or 0),
            "latest_import": dict(latest) if latest else None,
            "source_updated_at": (latest or {}).get("source_updated_at") if latest else None,
            "snapshot_at": (latest or {}).get("snapshot_at") if latest else None,
        }

    def search_nearest(
        self,
        *,
        actor_type: str | None,
        city: str | None,
        municipality_code: str | None,
        lat: float | None,
        lng: float | None,
        limit: int,
        radius_km: float,
    ) -> dict[str, Any]:
        resolved_location = None
        match_scope = "none"
        no_results_reason = None

        if lat is not None and lng is not None:
            if not is_colombia_latlng(lat, lng):
                return {
                    "places": [],
                    "match_scope": "gps",
                    "resolved_location": {"lat": lat, "lng": lng},
                    "no_results_reason": "coordinates_outside_colombia",
                    "search_radius_km": radius_km,
                    "total_candidates": 0,
                    "geocoded_candidates": 0,
                }
            latitude_delta = radius_km / 111.0
            longitude_delta = radius_km / (111.0 * max(abs(math.cos(math.radians(lat))), 1e-6))
            stmt = _searchable_sites_statement(actor_type).where(
                places_sites.c.lat.is_not(None),
                places_sites.c.lng.is_not(None),
                places_sites.c.lat.between(lat - latitude_delta, lat + latitude_delta),
                places_sites.c.lng.between(lng - longitude_delta, lng + longitude_delta),
            )
            with self.engine.begin() as conn:
                geo = [dict(row) for row in conn.execute(stmt).mappings().all()]
            geo = [
                row for row in geo
                if is_colombia_latlng(float(row["lat"]), float(row["lng"]))
            ]
            ranked = []
            for row in geo:
                distance = _haversine(lat, lng, float(row["lat"]), float(row["lng"]))
                if distance <= radius_km:
                    ranked.append((distance, row))
            ranked.sort(key=lambda item: item[0])
            places = [
                _site_to_place_result(row, distance_km=dist, contact_available=True)
                for dist, row in ranked[:limit]
            ]
            if not places:
                no_results_reason = "no_affiliates_within_radius"
            return {
                "places": places,
                "match_scope": "gps",
                "resolved_location": {"lat": lat, "lng": lng},
                "no_results_reason": no_results_reason,
                "search_radius_km": radius_km,
                "total_candidates": len(ranked),
                "geocoded_candidates": len(geo),
            }

        # Municipality search — affiliates only, NO national fallback
        city_norm = (city or "").strip().lower()
        if municipality_code:
            stmt = _searchable_sites_statement(actor_type).where(
                places_sites.c.municipality_code == municipality_code
            )
            match_scope = "municipality_code"
            resolved_location = {"municipality_code": municipality_code}
        elif city_norm:
            stmt = _searchable_sites_statement(actor_type).where(
                or_(
                    func.lower(places_sites.c.municipality) == city_norm,
                    func.lower(places_sites.c.raw_city) == city_norm,
                )
            )
            match_scope = "municipality_name"
            resolved_location = {"city": city}
        else:
            return {
                "places": [],
                "match_scope": "none",
                "resolved_location": None,
                "no_results_reason": "city_or_coordinates_required",
                "search_radius_km": radius_km,
                "total_candidates": 0,
                "geocoded_candidates": 0,
            }

        with self.engine.begin() as conn:
            filtered = [dict(row) for row in conn.execute(stmt).mappings().all()]
        if not filtered:
            return {
                "places": [],
                "match_scope": match_scope,
                "resolved_location": resolved_location,
                "no_results_reason": "no_affiliates_in_municipality",
                "search_radius_km": radius_km,
                "total_candidates": 0,
                "geocoded_candidates": 0,
            }

        filtered.sort(
            key=lambda r: (
                -(r.get("quality_score") or 0),
                r.get("name") or "",
            )
        )
        places = [_site_to_place_result(row, contact_available=True) for row in filtered[:limit]]
        return {
            "places": places,
            "match_scope": match_scope,
            "resolved_location": resolved_location,
            "no_results_reason": None,
            "search_radius_km": radius_km,
            "total_candidates": len(filtered),
            "geocoded_candidates": sum(1 for r in filtered if r.get("lat") is not None),
        }

    def list_partners(self) -> list[dict[str, Any]]:
        with self.engine.begin() as conn:
            rows = conn.execute(
                select(places_sites)
                .where(places_sites.c.is_partner == True)  # noqa: E712
                .where(places_sites.c.operational_status.notin_(list(EXCLUDED_STATUSES)))
                .where(_effective_presence_clause())
                .order_by(places_sites.c.municipality, places_sites.c.name)
            ).mappings().all()
        return [
            {
                "id": r["site_id"],
                "name": r["name"],
                "city": r["municipality"],
                "department": r["department"],
                "kind": r["actor_type"],
            }
            for r in rows
        ]

    def list_geojson_features(
        self, *, city: str, department: str | None = None
    ) -> list[dict[str, Any]]:
        """Return GeoJSON features for sites with coordinates in a municipality."""
        from places_service.domain.models import CONFIRMED_VALIDATION_STATUSES

        city_norm = (city or "").strip().casefold()
        dept_norm = (department or "").strip().casefold() or None
        with self.engine.begin() as conn:
            rows = conn.execute(
                select(places_sites)
                .where(places_sites.c.lat.is_not(None))
                .where(places_sites.c.lng.is_not(None))
                .where(_effective_presence_clause())
                .order_by(places_sites.c.actor_type, places_sites.c.name)
            ).mappings().all()
        features: list[dict[str, Any]] = []
        for row in rows:
            if (row.get("municipality") or "").strip().casefold() != city_norm:
                continue
            if dept_norm and (row.get("department") or "").strip().casefold() != dept_norm:
                continue
            validation = row.get("geocode_validation_status")
            location_confirmed = (
                str(validation) in CONFIRMED_VALIDATION_STATUSES if validation else False
            )
            features.append(
                {
                    "type": "Feature",
                    "geometry": {
                        "type": "Point",
                        "coordinates": [float(row["lng"]), float(row["lat"])],
                    },
                    "properties": {
                        "id": row["site_id"],
                        "source_place_id": row.get("source_place_id"),
                        "name": row["name"],
                        "kind": row["actor_type"],
                        "address": row["address_raw"],
                        "city": row["municipality"],
                        "department": row["department"],
                        "precision": row.get("location_precision"),
                        "validation_status": validation,
                        "confidence": row.get("geocode_confidence"),
                        "provider": row.get("geocode_provider"),
                        "location_confirmed": location_confirmed,
                    },
                }
            )
        return features


_HASH_EXCLUDED_FIELDS = frozenset(
    {
        "created_at",
        "updated_at",
        "import_run_id",
        "first_seen_import_run",
        "last_seen_import_run",
        "last_seen_import_run_id",
        "missing_since_import_run",
        "first_seen_at",
        "last_seen_at",
        "content_hash",
        "snapshot_presence",
        "source_presence_status",
        "present_in_latest_snapshot",
    }
)


def _content_hash(payload: dict[str, Any]) -> str:
    """Hash only canonical content, never import or lifecycle metadata."""
    content = {key: value for key, value in payload.items() if key not in _HASH_EXCLUDED_FIELDS}
    encoded = json.dumps(content, ensure_ascii=False, sort_keys=True, separators=(",", ":"), default=str)
    return hashlib.sha256(encoded.encode("utf-8")).hexdigest()


def _legacy_site_payload(site: Site, payload: dict[str, Any], import_run: ImportRun) -> dict[str, Any]:
    return {
        "id": site.site_id,
        "name": site.name,
        "address": site.address_raw or site.address_normalized,
        "city": site.municipality,
        "department": site.department,
        "kind": site.actor_type,
        "lat": site.lat,
        "lng": site.lng,
        "is_partner": payload["is_partner"],
        "phone": None,
        "status": site.operational_status,
        "source": "runt",
        "source_updated_at": import_run.source_updated_at,
        "geocode_confidence": site.geocode_confidence,
        "geocode_provider": site.geocode_provider,
        "geocode_status": site.geocode_status,
        "runt_actor_id": site.source_actor_id,
        "nit": None,
        "is_bookable": payload["is_bookable"],
        "booking_mode": payload["booking_mode"],
        "municipality_code": site.municipality_code,
        "status_verified": site.status_verified,
        "location_precision": site.location_precision,
    }


def _import_run_payload(
    import_run: ImportRun,
    *,
    status: str,
    completed_at: str | None,
    counts: dict[str, int] | None = None,
    error_code: str | None = None,
    error_message: str | None = None,
    failed_at: str | None = None,
) -> dict[str, Any]:
    counts = counts or {}
    return {
        "import_run_id": import_run.import_run_id,
        "source_name": import_run.source_name,
        "input_filename": import_run.input_filename,
        "input_sha256": import_run.input_sha256,
        "started_at": import_run.started_at,
        "completed_at": completed_at,
        "status": status,
        "source_record_count": import_run.source_record_count,
        "inserted_count": counts.get("inserted", 0),
        "updated_count": counts.get("updated", 0),
        "unchanged_count": counts.get("unchanged", 0),
        "merged_count": import_run.merged_count,
        "rejected_count": import_run.rejected_count,
        "review_count": import_run.review_count,
        "report_path": import_run.report_path,
        "source_updated_at": import_run.source_updated_at,
        "snapshot_at": import_run.snapshot_at,
        "missing_count": counts.get("missing", 0),
        "reappeared_count": counts.get("reappeared", 0),
        "error_code": error_code,
        "error_message": error_message,
        "failed_at": failed_at,
    }


def _upsert(engine: Engine, table, payload: dict[str, Any], *, pk: str):
    dialect = engine.dialect.name
    if dialect == "sqlite":
        stmt = sqlite_insert(table).values(**payload)
        update_cols = {c.name: stmt.excluded[c.name] for c in table.columns if c.name != pk}
        return stmt.on_conflict_do_update(index_elements=[pk], set_=update_cols)
    if dialect == "postgresql":
        stmt = pg_insert(table).values(**payload)
        update_cols = {c.name: stmt.excluded[c.name] for c in table.columns if c.name != pk}
        return stmt.on_conflict_do_update(index_elements=[pk], set_=update_cols)
    # generic fallback
    return table.insert().prefix_with("OR REPLACE").values(**payload) if dialect == "sqlite" else table.insert().values(**payload)


def _haversine(lat1: float, lng1: float, lat2: float, lng2: float) -> float:
    radius = 6371.0
    dlat = math.radians(lat2 - lat1)
    dlng = math.radians(lng2 - lng1)
    a = (
        math.sin(dlat / 2) ** 2
        + math.cos(math.radians(lat1)) * math.cos(math.radians(lat2)) * math.sin(dlng / 2) ** 2
    )
    return radius * 2 * math.atan2(math.sqrt(a), math.sqrt(1 - a))


def _bool_as_int(condition):
    """Portable conditional count expression for SQLite and PostgreSQL."""
    return case((condition, 1), else_=0)


def _insert_presence_event(
    conn,
    *,
    site_id: str,
    import_run_id: str,
    previous_status: str | None,
    new_status: str,
    event_type: str,
    reason: str,
    created_at: str,
) -> None:
    conn.execute(
        places_presence_events.insert().values(
            event_id=str(uuid4()),
            site_id=site_id,
            import_run_id=import_run_id,
            previous_status=previous_status,
            new_status=new_status,
            event_type=event_type,
            reason=reason,
            actor="import_catalog",
            source="import_catalog",
            created_at=created_at,
        )
    )


def _grouped_counts(conn, column) -> dict[str, int]:
    rows = conn.execute(
        select(column, func.count()).select_from(places_sites).group_by(column)
    ).all()
    return {str(value): int(count) for value, count in rows if value is not None}


def _searchable_sites_statement(actor_type: str | None):
    """Affiliates bookable via Civi: partner + civi mode + ops WhatsApp."""
    stmt = (
        select(places_sites)
        .select_from(
            places_sites.join(
                places_contacts,
                and_(
                    places_contacts.c.site_id == places_sites.c.site_id,
                    places_contacts.c.contact_type == "ops_whatsapp",
                    places_contacts.c.is_valid == True,  # noqa: E712
                    places_contacts.c.e164.is_not(None),
                    places_contacts.c.e164 != "",
                ),
            )
        )
        .where(places_sites.c.operational_status.notin_(list(EXCLUDED_STATUSES)))
        .where(_effective_presence_clause())
        .where(places_sites.c.is_partner == True)  # noqa: E712
        .where(places_sites.c.is_bookable == True)  # noqa: E712
        .where(places_sites.c.booking_mode == "civi")
        .distinct()
    )
    if actor_type:
        stmt = stmt.where(places_sites.c.actor_type == actor_type.upper())
    return stmt


def _effective_presence_clause():
    """Single presence rule shared by nearest, partners, and eligibility surfaces."""
    return places_sites.c.source_presence_status.in_(
        ("present", "reappeared", "manually_preserved")
    )


def _normalize_e164(value: str) -> str:
    digits = "".join(ch for ch in (value or "").strip() if ch.isdigit())
    return digits


def _site_to_place_result(
    row: dict[str, Any],
    *,
    distance_km: float | None = None,
    contact_available: bool = False,
) -> dict[str, Any]:
    from places_service.domain.models import CONFIRMED_VALIDATION_STATUSES

    validation_status = row.get("geocode_validation_status")
    location_confirmed = (
        str(validation_status) in CONFIRMED_VALIDATION_STATUSES if validation_status else None
    )
    precision = row.get("location_precision")
    result = {
        "id": row["site_id"],
        "name": row["name"],
        "address": row["address_raw"],
        "city": row["municipality"],
        "department": row["department"],
        "kind": row["actor_type"],
        "distance_km": round(distance_km, 2) if distance_km is not None else None,
        "municipality_code": row.get("municipality_code"),
        "status": row.get("operational_status"),
        "status_verified": row.get("status_verified"),
        "is_partner": row.get("is_partner"),
        "is_bookable": row.get("is_bookable"),
        "booking_mode": row.get("booking_mode"),
        "location_precision": precision,
        "data_quality": row.get("quality_score"),
        "contact_available": contact_available,
        "lat": row.get("lat"),
        "lng": row.get("lng"),
        "confidence": row.get("geocode_confidence"),
        "provider": row.get("geocode_provider"),
        "precision": precision,
        "validation_status": validation_status,
        # approximate_not_confirmed must never be presented as confirmed
        "location_confirmed": location_confirmed,
    }
    return result


# Backward-compatible thin wrapper used by existing memory/sql seed paths.
class SqlPlacesRepository:
    def __init__(self, database_url: str, *, create_schema: bool = False, seed_catalog: bool = False) -> None:
        self.catalog = CatalogSqlRepository(database_url, create_schema=create_schema)
        self.engine = self.catalog.engine
        if seed_catalog:
            self._seed_catalog_if_empty()

    def list_all(self) -> list[Place]:
        with self.engine.begin() as conn:
            rows = conn.execute(select(places).order_by(places.c.city, places.c.name)).mappings().all()
        return [_legacy_place_from_row(row) for row in rows]

    def list_partners(self) -> list[Place]:
        with self.engine.begin() as conn:
            rows = conn.execute(
                select(places).where(places.c.is_partner == True).order_by(places.c.city, places.c.name)  # noqa: E712
            ).mappings().all()
        return [_legacy_place_from_row(row) for row in rows]

    def upsert_places(self, rows: list[Place]) -> int:
        payloads = [_legacy_place_to_row(place) for place in rows]
        with self.engine.begin() as conn:
            for payload in payloads:
                conn.execute(_upsert(self.engine, places, payload, pk="id"))
        return len(payloads)

    def _seed_catalog_if_empty(self) -> None:
        with self.engine.begin() as conn:
            existing = conn.execute(select(places.c.id).limit(1)).first()
            if existing is not None:
                return
            for place in PLACES:
                conn.execute(places.insert().values(**_legacy_place_to_row(place)))


def _legacy_place_to_row(place: Place) -> dict[str, Any]:
    return {
        "id": place.id,
        "name": place.name,
        "address": place.address,
        "city": place.city,
        "department": place.department,
        "kind": place.kind,
        "lat": place.lat,
        "lng": place.lng,
        "is_partner": place.is_partner,
        "phone": place.phone,
        "status": place.status,
        "source": place.source,
        "source_updated_at": place.source_updated_at,
        "geocode_confidence": place.geocode_confidence,
        "geocode_provider": place.geocode_provider,
        "geocode_status": place.geocode_status,
        "runt_actor_id": place.runt_actor_id,
        "nit": place.nit,
        "is_bookable": getattr(place, "is_bookable", False),
        "booking_mode": getattr(place, "booking_mode", "information_only"),
        "municipality_code": getattr(place, "municipality_code", None),
        "status_verified": getattr(place, "status_verified", False),
        "location_precision": getattr(place, "location_precision", None),
    }


def _legacy_place_from_row(row) -> Place:
    return Place(
        id=str(row["id"]),
        name=str(row["name"]),
        address=str(row["address"]),
        city=str(row["city"]),
        department=str(row["department"]),
        kind=str(row["kind"]),
        lat=float(row["lat"]) if row["lat"] is not None else None,
        lng=float(row["lng"]) if row["lng"] is not None else None,
        is_partner=bool(row["is_partner"]),
        phone=str(row["phone"]) if row.get("phone") is not None else None,
        status=str(row["status"] or "unknown"),
        source=str(row["source"] or "catalog"),
        source_updated_at=str(row["source_updated_at"]) if row.get("source_updated_at") else None,
        geocode_confidence=float(row["geocode_confidence"]) if row.get("geocode_confidence") is not None else None,
        geocode_provider=str(row["geocode_provider"]) if row.get("geocode_provider") else None,
        geocode_status=str(row["geocode_status"] or "skipped"),
        runt_actor_id=str(row["runt_actor_id"]) if row.get("runt_actor_id") else None,
        nit=str(row["nit"]) if row.get("nit") else None,
        is_bookable=bool(row["is_bookable"]) if "is_bookable" in row.keys() else False,
        booking_mode=str(row["booking_mode"] or "information_only") if "booking_mode" in row.keys() else "information_only",
        municipality_code=str(row["municipality_code"]) if row.get("municipality_code") else None,
        status_verified=bool(row["status_verified"]) if "status_verified" in row.keys() else False,
        location_precision=str(row["location_precision"]) if row.get("location_precision") else None,
    )


def catalog_repository_from_env() -> CatalogSqlRepository | None:
    mode = os.getenv("PLACES_REPOSITORY_MODE", "memory").strip().lower()
    if mode != "sql":
        return None
    database_url = os.getenv("PLACES_DATABASE_URL", "").strip()
    if not database_url:
        return None
    auto_create = os.getenv("PLACES_AUTO_CREATE_SCHEMA", "").strip().lower() in {"1", "true", "yes"}
    return CatalogSqlRepository(database_url, create_schema=auto_create)
