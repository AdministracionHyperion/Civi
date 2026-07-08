from __future__ import annotations

from fastapi import APIRouter, Depends

from civi_common import require_internal_token

from .schemas import ListDocumentTypesResponse
from .use_case import list_document_types

router = APIRouter(prefix="/internal/runt", dependencies=[Depends(require_internal_token)])


@router.get("/tipos-documento", response_model=ListDocumentTypesResponse)
async def get_document_types() -> ListDocumentTypesResponse:
    return await list_document_types()
