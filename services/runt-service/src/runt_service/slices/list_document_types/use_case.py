from __future__ import annotations

from .schemas import DocumentType, ListDocumentTypesResponse


async def list_document_types() -> ListDocumentTypesResponse:
    return ListDocumentTypesResponse(
        document_types=[
            DocumentType(code="CC", label="Cedula de ciudadania"),
            DocumentType(code="CE", label="Cedula de extranjeria"),
            DocumentType(code="NIT", label="NIT"),
            DocumentType(code="TI", label="Tarjeta de identidad"),
        ]
    )
