from __future__ import annotations

from pydantic import BaseModel


class CancelAppointmentResponse(BaseModel):
    success: bool
    appointment: dict[str, object] | None = None
    error: str | None = None
