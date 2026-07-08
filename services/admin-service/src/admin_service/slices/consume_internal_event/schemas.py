from __future__ import annotations

from pydantic import BaseModel, Field


class ConsumeInternalEventRequest(BaseModel):
    event_id: str = Field(min_length=1, max_length=128)
    event_type: str = Field(min_length=1, max_length=96)
    producer: str = Field(min_length=1, max_length=96)
    schema_version: str = Field(default="1", min_length=1, max_length=16)
    occurred_at: str | None = Field(default=None, max_length=64)
    correlation_id: str | None = Field(default=None, max_length=128)
    user_key: str | None = Field(default=None, max_length=256)
    channel: str | None = Field(default=None, max_length=32)
    appointment_id: int | None = None
    reminder_id: int | None = None
    message_id: int | None = None
    status: str | None = Field(default=None, max_length=32)
    provider: str | None = Field(default=None, max_length=96)
    to_tail: str | None = Field(default=None, max_length=16)


class ConsumeInternalEventResponse(BaseModel):
    success: bool = True
    audit_event_id: int
