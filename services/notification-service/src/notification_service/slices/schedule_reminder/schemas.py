from __future__ import annotations

from pydantic import BaseModel, Field


class ScheduleReminderRequest(BaseModel):
    user_key: str = Field(min_length=1)
    to: str = Field(min_length=6, max_length=32)
    body: str = Field(min_length=1, max_length=4096)
    remind_at: str = Field(min_length=10)


class ScheduleReminderResponse(BaseModel):
    success: bool = True
    reminder: dict[str, object]
