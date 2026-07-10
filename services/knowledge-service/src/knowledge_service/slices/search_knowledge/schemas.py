from __future__ import annotations

from pydantic import BaseModel, Field


class SearchKnowledgeRequest(BaseModel):
    query: str = Field(min_length=2, max_length=1000)
    domain: str | None = Field(default=None, max_length=64)
    limit: int = Field(default=5, ge=1, le=10)


class KnowledgeHit(BaseModel):
    id: str
    title: str
    body: str
    domain: str
    score: float


class SearchKnowledgeResponse(BaseModel):
    success: bool
    hits: list[KnowledgeHit] = Field(default_factory=list)
    message: str | None = None
