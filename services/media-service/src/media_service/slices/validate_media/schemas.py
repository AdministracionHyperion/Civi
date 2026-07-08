from __future__ import annotations

from pydantic import BaseModel, Field


class ValidateMediaRequest(BaseModel):
    content_type: str = Field(min_length=3)
    size_bytes: int = Field(ge=0)


class ValidateMediaResponse(BaseModel):
    success: bool
    media_kind: str | None = None
    error: str | None = None
