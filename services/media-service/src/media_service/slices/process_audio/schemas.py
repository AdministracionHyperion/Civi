from __future__ import annotations

from pydantic import BaseModel, Field


class ProcessAudioRequest(BaseModel):
    content_type: str = Field(min_length=3)
    size_bytes: int = Field(ge=0)
    media_ref: str = Field(min_length=1)


class ProcessAudioResponse(BaseModel):
    success: bool
    job_id: int | None = None
    transcript: str | None = None
    error: str | None = None
    provider_mode: str = "disabled"
