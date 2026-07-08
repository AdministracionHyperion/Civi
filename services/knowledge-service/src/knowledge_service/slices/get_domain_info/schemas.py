from __future__ import annotations

from pydantic import BaseModel, Field


class GetDomainInfoRequest(BaseModel):
    domain: str = Field(min_length=2, max_length=64)
    topic: str = Field(min_length=2, max_length=64)


class GetDomainInfoResponse(BaseModel):
    success: bool
    domain: str
    topic: str
    title: str | None = None
    body: str | None = None
    available_topics: list[str] = Field(default_factory=list)
    message: str | None = None
