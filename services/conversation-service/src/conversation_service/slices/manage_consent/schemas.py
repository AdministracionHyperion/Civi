from __future__ import annotations

from typing import Literal

from pydantic import BaseModel, Field


ConsentStatus = Literal["accepted", "declined", "unknown"]


class UpdateConsentRequest(BaseModel):
    user_key: str = Field(min_length=1)
    channel: str = "web"
    status: Literal["accepted", "declined"]
    purpose: str = Field(default="civi_conversation", min_length=3, max_length=128)
    policy_version: str = Field(default="2026-07-07", min_length=4, max_length=64)


class ConsentResponse(BaseModel):
    user_key: str
    channel: str
    status: ConsentStatus
    purpose: str
    policy_version: str
    updated_at: str | None = None
