from __future__ import annotations

from pydantic import BaseModel


class ConfirmAppointmentResponse(BaseModel):
    success: bool = True
    appointment: dict[str, object] | None = None
    error: str | None = None
    notifications: dict[str, object] | None = None
