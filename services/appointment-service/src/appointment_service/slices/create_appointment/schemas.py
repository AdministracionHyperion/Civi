from __future__ import annotations

from pydantic import BaseModel, Field


class AppointmentPlace(BaseModel):
    id: str = Field(min_length=1)
    name: str = Field(min_length=1)
    address: str = Field(min_length=1)
    city: str = Field(min_length=1)


class CreateAppointmentRequest(BaseModel):
    user_key: str = Field(min_length=1)
    procedure: str = Field(min_length=2)
    starts_at: str = Field(min_length=10)
    place: AppointmentPlace
    notification_to: str | None = Field(default=None, min_length=6, max_length=32)


class CreateAppointmentResponse(BaseModel):
    success: bool = True
    appointment: dict[str, object]
    notification: dict[str, object] | None = None
