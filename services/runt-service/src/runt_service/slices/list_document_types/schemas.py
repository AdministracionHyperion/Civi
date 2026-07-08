from __future__ import annotations

from pydantic import BaseModel


class DocumentType(BaseModel):
    code: str
    label: str


class ListDocumentTypesResponse(BaseModel):
    document_types: list[DocumentType]
