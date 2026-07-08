from __future__ import annotations

from pydantic import BaseModel, Field


class ListAppointmentsResponse(BaseModel):
    success: bool = True
    appointments: list[dict[str, object]] = Field(default_factory=list)
