from __future__ import annotations

from fastapi import APIRouter, Depends

from civi_common import require_internal_token
from places_service.adapters.outbound.catalog_repository import catalog_repository_from_env

from .schemas import PlaceDetailResponse

router = APIRouter(tags=["places"])


@router.get(
    "/internal/places/{site_id}",
    response_model=PlaceDetailResponse,
    dependencies=[Depends(require_internal_token)],
)
async def get_place(site_id: str) -> PlaceDetailResponse:
    repo = catalog_repository_from_env()
    if repo is None:
        return PlaceDetailResponse(success=False, place=None, error="catalog_repository_unavailable")
    site = repo.get_site(site_id)
    if site is None:
        return PlaceDetailResponse(success=False, place=None, error="not_found")
    return PlaceDetailResponse(success=True, place=site)
