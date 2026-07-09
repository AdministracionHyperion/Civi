from __future__ import annotations

import json
import math
import os
from dataclasses import asdict
from typing import Any

from sqlalchemy import and_, func, or_, select
from sqlalchemy.dialects.postgresql import insert as pg_insert
from sqlalchemy.dialects.sqlite import insert as sqlite_insert
from sqlalchemy.engine import Engine

from civi_common.geo import is_colombia_latlng
from places_service.adapters.outbound.schema import (
    create_all_tables,
    create_engine_from_url,
    places,
    places_contacts,
    places_duplicate_candidates,
    places_entities,
    places_import_runs,
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
            create_all_tables(self.engine)

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
        existing_partners: dict[str, dict[str, Any]] = {}
        if preserve_partner_flags:
            with self.engine.begin() as conn:
                rows = conn.execute(
                    select(
                        places_sites.c.site_id,
                        places_sites.c.is_partner,
                        places_sites.c.is_bookable,
                        places_sites.c.booking_mode,
                    )
                ).mappings().all()
                for row in rows:
                    if row["is_partner"] or row["is_bookable"]:
                        existing_partners[str(row["site_id"])] = dict(row)

        inserted = updated = unchanged = 0
        with self.engine.begin() as conn:
            # import run
            conn.execute(
                _upsert(
                    self.engine,
                    places_import_runs,
                    {
                        "import_run_id": import_run.import_run_id,
                        "source_name": import_run.source_name,
                        "input_filename": import_run.input_filename,
                        "input_sha256": import_run.input_sha256,
                        "started_at": import_run.started_at,
                        "completed_at": import_run.completed_at,
                        "status": import_run.status,
                        "source_record_count": import_run.source_record_count,
                        "inserted_count": import_run.inserted_count,
                        "updated_count": import_run.updated_count,
                        "unchanged_count": import_run.unchanged_count,
                        "merged_count": import_run.merged_count,
                        "rejected_count": import_run.rejected_count,
                        "review_count": import_run.review_count,
                        "report_path": import_run.report_path,
                        "source_updated_at": import_run.source_updated_at,
                        "snapshot_at": import_run.snapshot_at,
                    },
                    pk="import_run_id",
                )
            )

            for entity in entities:
                payload = asdict(entity)
                existed = conn.execute(
                    select(places_entities.c.entity_id).where(places_entities.c.entity_id == entity.entity_id)
                ).first()
                conn.execute(_upsert(self.engine, places_entities, payload, pk="entity_id"))
                if existed:
                    updated += 1
                else:
                    inserted += 1

            for site in sites:
                payload = asdict(site)
                if site.site_id in existing_partners:
                    preserved = existing_partners[site.site_id]
                    payload["is_partner"] = preserved["is_partner"]
                    payload["is_bookable"] = preserved["is_bookable"]
                    payload["booking_mode"] = preserved["booking_mode"]
                existed = conn.execute(
                    select(places_sites.c.site_id).where(places_sites.c.site_id == site.site_id)
                ).first()
                conn.execute(_upsert(self.engine, places_sites, payload, pk="site_id"))
                # mirror legacy places row for transitional compatibility
                conn.execute(
                    _upsert(
                        self.engine,
                        places,
                        {
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
                        },
                        pk="id",
                    )
                )
                if existed:
                    updated += 1
                else:
                    inserted += 1

            for contact in contacts:
                conn.execute(_upsert(self.engine, places_contacts, asdict(contact), pk="contact_id"))

            for rec in source_records:
                payload = asdict(rec)
                payload["source_payload"] = json.dumps(payload["source_payload"], ensure_ascii=False)
                payload["processing_flags"] = json.dumps(payload["processing_flags"], ensure_ascii=False)
                conn.execute(_upsert(self.engine, places_source_records, payload, pk="source_record_id"))

            for cand in duplicate_candidates:
                conn.execute(_upsert(self.engine, places_duplicate_candidates, asdict(cand), pk="candidate_id"))

        return {"inserted": inserted, "updated": updated, "unchanged": unchanged}

    def get_site(self, site_id: str) -> dict[str, Any] | None:
        with self.engine.begin() as conn:
            row = conn.execute(select(places_sites).where(places_sites.c.site_id == site_id)).mappings().first()
        return dict(row) if row else None

    def booking_eligibility(self, site_id: str) -> dict[str, Any]:
        site = self.get_site(site_id)
        if site is None:
            return {
                "site_id": site_id,
                "exists": False,
                "is_partner": False,
                "is_bookable": False,
                "booking_mode": "unavailable",
                "operational_status": "unknown",
                "canonical_name": None,
                "canonical_address": None,
                "canonical_city": None,
            }
        return {
            "site_id": site_id,
            "exists": True,
            "is_partner": bool(site["is_partner"]),
            "is_bookable": bool(site["is_bookable"]),
            "booking_mode": site["booking_mode"],
            "operational_status": site["operational_status"],
            "canonical_name": site["name"],
            "canonical_address": site["address_raw"],
            "canonical_city": site["municipality"],
        }

    def catalog_summary(self) -> dict[str, Any]:
        with self.engine.begin() as conn:
            sites = conn.execute(select(places_sites)).mappings().all()
            entities = conn.execute(select(func.count()).select_from(places_entities)).scalar_one()
            source_records = conn.execute(select(func.count()).select_from(places_source_records)).scalar_one()
            dupes = conn.execute(select(func.count()).select_from(places_duplicate_candidates)).scalar_one()
            latest = conn.execute(
                select(places_import_runs).order_by(places_import_runs.c.started_at.desc()).limit(1)
            ).mappings().first()
        by_type: dict[str, int] = {}
        by_status: dict[str, int] = {}
        for site in sites:
            by_type[site["actor_type"]] = by_type.get(site["actor_type"], 0) + 1
            by_status[site["operational_status"]] = by_status.get(site["operational_status"], 0) + 1
        return {
            "source_records": int(source_records or 0),
            "unique_entities": int(entities or 0),
            "unique_sites": len(sites),
            "by_actor_type": by_type,
            "by_operational_status": by_status,
            "partners": sum(1 for s in sites if s["is_partner"]),
            "bookable": sum(1 for s in sites if s["is_bookable"]),
            "geocoded": sum(1 for s in sites if s["lat"] is not None and s["lng"] is not None),
            "pending_geocoding": sum(1 for s in sites if s["geocode_status"] in {"not_attempted", "pending"}),
            "manual_review": sum(1 for s in sites if s["requires_manual_review"]),
            "duplicate_candidates": int(dupes or 0),
            "invalid_addresses": sum(1 for s in sites if s["address_quality"] in {"invalid", "missing"}),
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
        with self.engine.begin() as conn:
            stmt = select(places_sites).where(
                places_sites.c.operational_status.notin_(list(EXCLUDED_STATUSES))
            )
            if actor_type:
                stmt = stmt.where(places_sites.c.actor_type == actor_type.upper())
            rows = [dict(r) for r in conn.execute(stmt).mappings().all()]

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
            geo = [r for r in rows if r["lat"] is not None and r["lng"] is not None and is_colombia_latlng(float(r["lat"]), float(r["lng"]))]
            ranked = []
            for row in geo:
                distance = _haversine(lat, lng, float(row["lat"]), float(row["lng"]))
                if distance <= radius_km:
                    ranked.append((distance, row))
            ranked.sort(key=lambda item: (item[0], not item[1]["is_bookable"], not item[1]["is_partner"]))
            places = [_site_to_place_result(row, distance_km=dist) for dist, row in ranked[:limit]]
            if not places:
                no_results_reason = "no_sites_within_radius"
            return {
                "places": places,
                "match_scope": "gps",
                "resolved_location": {"lat": lat, "lng": lng},
                "no_results_reason": no_results_reason,
                "search_radius_km": radius_km,
                "total_candidates": len(ranked),
                "geocoded_candidates": len(geo),
            }

        # Municipality search — NO national fallback
        city_norm = (city or "").strip().lower()
        filtered = rows
        if municipality_code:
            filtered = [r for r in rows if (r.get("municipality_code") or "") == municipality_code]
            match_scope = "municipality_code"
            resolved_location = {"municipality_code": municipality_code}
        elif city_norm:
            filtered = [
                r
                for r in rows
                if (r.get("municipality") or "").strip().lower() == city_norm
                or (r.get("raw_city") or "").strip().lower() == city_norm
            ]
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

        if not filtered:
            return {
                "places": [],
                "match_scope": match_scope,
                "resolved_location": resolved_location,
                "no_results_reason": "no_coverage_in_municipality",
                "search_radius_km": radius_km,
                "total_candidates": 0,
                "geocoded_candidates": 0,
            }

        filtered.sort(
            key=lambda r: (
                not r["is_bookable"],
                not r["is_partner"],
                -(r.get("quality_score") or 0),
                r.get("name") or "",
            )
        )
        places = [_site_to_place_result(row) for row in filtered[:limit]]
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


def _site_to_place_result(row: dict[str, Any], *, distance_km: float | None = None) -> dict[str, Any]:
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
        "location_precision": row.get("location_precision"),
        "data_quality": row.get("quality_score"),
        "contact_available": False,
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
