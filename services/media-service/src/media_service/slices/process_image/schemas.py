from __future__ import annotations

from pydantic import BaseModel, Field


class ProcessImageRequest(BaseModel):
    content_type: str = Field(min_length=3)
    size_bytes: int = Field(ge=0)
    media_ref: str = Field(min_length=1)
    content_base64: str | None = None


class ProcessImageResponse(BaseModel):
    success: bool
    job_id: int | None = None
    extracted_text: str | None = None
    error: str | None = None
    provider_mode: str = "disabled"
