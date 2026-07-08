from __future__ import annotations

from dataclasses import dataclass
from threading import Lock
from typing import Any


@dataclass
class PendingAppointmentSelection:
    user_key: str
    channel: str
    procedure: str
    places: list[dict[str, Any]]
    starts_at: str | None = None
    selected_index: int | None = None


@dataclass
class PendingVehicleConsult:
    user_key: str
    channel: str
    intent: str


class InMemoryAppointmentSelectionStore:
    def __init__(self) -> None:
        self._items: dict[tuple[str, str], PendingAppointmentSelection] = {}
        self._lock = Lock()

    def get(self, *, user_key: str, channel: str) -> PendingAppointmentSelection | None:
        return self._items.get((user_key, channel.lower()))

    def save(self, selection: PendingAppointmentSelection) -> PendingAppointmentSelection:
        with self._lock:
            self._items[(selection.user_key, selection.channel.lower())] = selection
            return selection

    def clear(self, *, user_key: str, channel: str) -> None:
        with self._lock:
            self._items.pop((user_key, channel.lower()), None)

    def clear_all(self) -> None:
        with self._lock:
            self._items.clear()


appointment_selection_store = InMemoryAppointmentSelectionStore()


class InMemoryVehicleConsultStore:
    def __init__(self) -> None:
        self._items: dict[tuple[str, str], PendingVehicleConsult] = {}
        self._lock = Lock()

    def get(self, *, user_key: str, channel: str) -> PendingVehicleConsult | None:
        return self._items.get((user_key, channel.lower()))

    def save(self, pending: PendingVehicleConsult) -> PendingVehicleConsult:
        with self._lock:
            self._items[(pending.user_key, pending.channel.lower())] = pending
            return pending

    def clear(self, *, user_key: str, channel: str) -> None:
        with self._lock:
            self._items.pop((user_key, channel.lower()), None)

    def clear_all(self) -> None:
        with self._lock:
            self._items.clear()


vehicle_consult_store = InMemoryVehicleConsultStore()
