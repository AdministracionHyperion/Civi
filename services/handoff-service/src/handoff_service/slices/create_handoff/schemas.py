from __future__ import annotations

from pydantic import BaseModel, Field


class CreateHandoffRequest(BaseModel):
    user_key: str = Field(min_length=1, max_length=128)
    reason: str = Field(min_length=2, max_length=256)
    channel: str = Field(default="whatsapp", max_length=32)


class CreateHandoffResponse(BaseModel):
    handoff_id: str
    status: str
    message: str
