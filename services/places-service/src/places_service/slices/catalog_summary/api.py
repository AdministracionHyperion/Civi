from __future__ import annotations

from fastapi import APIRouter, Depends

from civi_common import require_internal_token
from places_service.adapters.outbound.catalog_repository import catalog_repository_from_env

from .schemas import CatalogSummaryResponse

router = APIRouter(tags=["places"])


@router.get(
    "/internal/places/catalog/summary",
    response_model=CatalogSummaryResponse,
    dependencies=[Depends(require_internal_token)],
)
async def catalog_summary() -> CatalogSummaryResponse:
    repo = catalog_repository_from_env()
    if repo is None:
        return CatalogSummaryResponse(success=False, error="catalog_repository_unavailable")
    return CatalogSummaryResponse(success=True, **repo.catalog_summary())
