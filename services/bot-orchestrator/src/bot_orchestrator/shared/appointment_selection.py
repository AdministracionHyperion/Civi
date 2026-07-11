from __future__ import annotations

import os
from dataclasses import dataclass
from threading import Lock
from typing import Any


AWAITING_PROCEDURE = "awaiting"


@dataclass
class PendingAppointmentSelection:
    user_key: str
    channel: str
    procedure: str
    places: list[dict[str, Any]]
    starts_at: str | None = None
    selected_index: int | None = None
    mentioned_crc: bool = False
    # Last appointment created in this selection flow (for corrections).
    created_appointment_id: int | None = None


@dataclass
class PendingVehicleConsult:
    user_key: str
    channel: str
    intent: str | None = None
    placa: str | None = None
    documento: str | None = None
    ciudad: str | None = None
    # For multas: True once the user gave a city or chose nacional/general.
    city_resolved: bool = False


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


@dataclass
class LastVehicleSlots:
    """Last placa/documento used for a SOAT/tecno consult on this channel."""

    user_key: str
    channel: str
    placa: str | None = None
    documento: str | None = None


class InMemoryLastVehicleSlotsStore:
    def __init__(self) -> None:
        self._items: dict[tuple[str, str], LastVehicleSlots] = {}
        self._lock = Lock()

    def get(self, *, user_key: str, channel: str) -> LastVehicleSlots | None:
        return self._items.get((user_key, channel.lower()))

    def save(self, slots: LastVehicleSlots) -> LastVehicleSlots:
        with self._lock:
            self._items[(slots.user_key, slots.channel.lower())] = slots
            return slots

    def clear(self, *, user_key: str, channel: str) -> None:
        with self._lock:
            self._items.pop((user_key, channel.lower()), None)

    def clear_all(self) -> None:
        with self._lock:
            self._items.clear()


last_vehicle_slots_store = InMemoryLastVehicleSlotsStore()


# ── Shared (cross-process) pending appointment store for WhatsApp async flow ──

class SharedPendingAppointmentStore:
    """Bridge: tries in-memory first (web channel), then falls back to SQL (worker)."""

    def __init__(self) -> None:
        self._sql: Any = None

    def _get_sql(self) -> Any:
        if self._sql is None:
            self._sql = _pending_store_from_env()
        return self._sql

    def save(self, *, user_key: str, channel: str, procedure: str) -> None:
        store = self._get_sql()
        if store is not None:
            store.save(user_key=user_key, channel=channel, procedure=procedure)

    def pop_pending_procedure(self, *, user_key: str) -> str | None:
        store = self._get_sql()
        if store is None:
            return None
        row = store.get_and_clear(user_key=user_key)
        if row is None:
            return None
        return row["procedure"]


def _pending_store_from_env() -> Any | None:
    mode = os.getenv("BOT_CONSULT_REPOSITORY_MODE", "sql").strip().lower()
    if mode != "sql":
        return None
    database_url = os.getenv("BOT_CONSULT_DATABASE_URL", "").strip()
    if not database_url:
        return None
    auto_create = os.getenv("BOT_CONSULT_AUTO_CREATE_SCHEMA", "").strip().lower() in {"1", "true", "yes"}
    from bot_orchestrator.adapters.outbound.sql_repository import SqlPendingAppointmentStore

    return SqlPendingAppointmentStore(database_url, create_schema=auto_create)


shared_pending_store = SharedPendingAppointmentStore()
