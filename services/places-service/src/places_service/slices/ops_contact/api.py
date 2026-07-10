from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException

from civi_common import require_internal_token
from places_service.adapters.outbound.catalog_repository import catalog_repository_from_env

from .schemas import OpsContactLookupRequest, OpsContactResponse

router = APIRouter(tags=["places"])


@router.get(
    "/internal/places/{site_id}/ops-contact",
    response_model=OpsContactResponse,
    dependencies=[Depends(require_internal_token)],
)
async def get_ops_contact(site_id: str) -> OpsContactResponse:
    repo = catalog_repository_from_env()
    if repo is None:
        raise HTTPException(status_code=503, detail="catalog_repository_unavailable")
    contact = repo.get_ops_contact(site_id)
    if contact is None:
        raise HTTPException(status_code=404, detail="ops_contact_not_found")
    return OpsContactResponse(**contact)


@router.post(
    "/internal/places/ops-contact/lookup",
    response_model=OpsContactResponse,
    dependencies=[Depends(require_internal_token)],
)
async def lookup_ops_contact(payload: OpsContactLookupRequest) -> OpsContactResponse:
    repo = catalog_repository_from_env()
    if repo is None:
        raise HTTPException(status_code=503, detail="catalog_repository_unavailable")
    contact = repo.lookup_by_ops_whatsapp(payload.e164)
    if contact is None:
        raise HTTPException(status_code=404, detail="ops_contact_not_found")
    return OpsContactResponse(**contact)
