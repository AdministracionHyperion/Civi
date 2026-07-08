from __future__ import annotations

from typing import Any

from pydantic import BaseModel, Field


class AgentTurnRequest(BaseModel):
    user_key: str = Field(min_length=1)
    text: str = Field(min_length=1)
    channel: str = "web"
    metadata: dict[str, Any] = Field(default_factory=dict)


class AgentTurnResponse(BaseModel):
    text: str
    state_version: int = 1
    mode: str = "agent_menu"
    tool_calls: list[str] = Field(default_factory=list)
