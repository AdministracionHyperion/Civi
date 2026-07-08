from __future__ import annotations

import os
from typing import Protocol

from places_service.shared.catalog import PLACES, Place


class PlacesRepository(Protocol):
    def list_all(self) -> list[Place]:
        ...

    def list_partners(self) -> list[Place]:
        ...


class InMemoryPlacesRepository:
    def __init__(self, places: tuple[Place, ...] = PLACES) -> None:
        self._places = list(places)

    def list_all(self) -> list[Place]:
        return list(self._places)

    def list_partners(self) -> list[Place]:
        return [place for place in self._places if place.is_partner]


def repository_from_env() -> PlacesRepository:
    mode = os.getenv("PLACES_REPOSITORY_MODE", "memory").strip().lower()
    if mode in {"", "memory", "catalog"}:
        return InMemoryPlacesRepository()
    if mode == "sql":
        database_url = os.getenv("PLACES_DATABASE_URL", "").strip()
        if not database_url:
            raise RuntimeError("PLACES_DATABASE_URL is required when PLACES_REPOSITORY_MODE=sql")
        from places_service.adapters.outbound.sql_repository import SqlPlacesRepository

        auto_create = os.getenv("PLACES_AUTO_CREATE_SCHEMA", "").strip().lower() in {"1", "true", "yes"}
        auto_seed = os.getenv("PLACES_AUTO_SEED_CATALOG", "").strip().lower() in {"1", "true", "yes"}
        return SqlPlacesRepository(database_url, create_schema=auto_create, seed_catalog=auto_seed)
    raise RuntimeError(f"unsupported places repository mode: {mode}")


repository = repository_from_env()
