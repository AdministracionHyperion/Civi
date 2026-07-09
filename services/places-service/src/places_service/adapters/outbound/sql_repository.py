from __future__ import annotations

"""Compatibility shim — prefer catalog_repository.SqlPlacesRepository."""

from places_service.adapters.outbound.catalog_repository import SqlPlacesRepository
from places_service.adapters.outbound.schema import metadata

__all__ = ["SqlPlacesRepository", "metadata"]
