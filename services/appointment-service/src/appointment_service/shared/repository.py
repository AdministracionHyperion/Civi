from __future__ import annotations

from dataclasses import dataclass, field
from datetime import UTC, datetime
from itertools import count
import os
from threading import Lock
from typing import Protocol


@dataclass
class AppointmentRecord:
    id: int
    user_key: str
    procedure: str
    place_id: str
    place_name: str
    place_address: str
    place_city: str
    starts_at: str
    status: str = "scheduled"
    created_at: str = field(default_factory=lambda: datetime.now(UTC).isoformat(timespec="seconds"))


class AppointmentRepository(Protocol):
    def create(
        self,
        *,
        user_key: str,
        procedure: str,
        place_id: str,
        place_name: str,
        place_address: str,
        place_city: str,
        starts_at: str,
    ) -> AppointmentRecord:
        ...

    def list_for_user(self, *, user_key: str) -> list[AppointmentRecord]:
        ...

    def cancel(self, *, user_key: str, appointment_id: int) -> AppointmentRecord | None:
        ...


class InMemoryAppointmentRepository:
    def __init__(self) -> None:
        self._records: dict[int, AppointmentRecord] = {}
        self._ids = count(1)
        self._lock = Lock()

    def create(
        self,
        *,
        user_key: str,
        procedure: str,
        place_id: str,
        place_name: str,
        place_address: str,
        place_city: str,
        starts_at: str,
    ) -> AppointmentRecord:
        with self._lock:
            record = AppointmentRecord(
                id=next(self._ids),
                user_key=user_key,
                procedure=procedure,
                place_id=place_id,
                place_name=place_name,
                place_address=place_address,
                place_city=place_city,
                starts_at=starts_at,
            )
            self._records[record.id] = record
            return record

    def list_for_user(self, *, user_key: str) -> list[AppointmentRecord]:
        return [
            record
            for record in sorted(self._records.values(), key=lambda item: item.starts_at)
            if record.user_key == user_key and record.status != "cancelled"
        ]

    def cancel(self, *, user_key: str, appointment_id: int) -> AppointmentRecord | None:
        with self._lock:
            record = self._records.get(appointment_id)
            if not record or record.user_key != user_key or record.status == "cancelled":
                return None
            record.status = "cancelled"
            return record


def repository_from_env() -> AppointmentRepository:
    mode = os.getenv("APPOINTMENT_REPOSITORY_MODE", "memory").strip().lower()
    if mode in {"", "memory"}:
        return InMemoryAppointmentRepository()
    if mode == "sql":
        database_url = os.getenv("APPOINTMENT_DATABASE_URL", "").strip()
        if not database_url:
            raise RuntimeError("APPOINTMENT_DATABASE_URL is required when APPOINTMENT_REPOSITORY_MODE=sql")
        from appointment_service.adapters.outbound.sql_repository import SqlAppointmentRepository

        auto_create = os.getenv("APPOINTMENT_AUTO_CREATE_SCHEMA", "").strip().lower() in {"1", "true", "yes"}
        return SqlAppointmentRepository(database_url, create_schema=auto_create)
    raise RuntimeError(f"unsupported appointment repository mode: {mode}")


repository = repository_from_env()
