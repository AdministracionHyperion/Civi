from __future__ import annotations

from dataclasses import dataclass, field
from datetime import UTC, datetime
from hashlib import sha256
import os
from threading import Lock
from typing import Protocol


@dataclass
class VehicleCacheRecord:
    cache_key: str
    payload: dict[str, object]
    created_at: str = field(default_factory=lambda: datetime.now(UTC).isoformat(timespec="seconds"))


class VehicleCacheRepository(Protocol):
    def get_vigencia(self, *, placa: str, documento: str, tipo_documento: str) -> VehicleCacheRecord | None:
        ...

    def save_vigencia(
        self,
        *,
        placa: str,
        documento: str,
        tipo_documento: str,
        payload: dict[str, object],
    ) -> VehicleCacheRecord:
        ...

    def get_multas(self, *, documento: str) -> VehicleCacheRecord | None:
        ...

    def save_multas(self, *, documento: str, payload: dict[str, object]) -> VehicleCacheRecord:
        ...


class InMemoryVehicleCacheRepository:
    def __init__(self) -> None:
        self._vigencia: dict[str, VehicleCacheRecord] = {}
        self._multas: dict[str, VehicleCacheRecord] = {}
        self._lock = Lock()

    def get_vigencia(self, *, placa: str, documento: str, tipo_documento: str) -> VehicleCacheRecord | None:
        return self._vigencia.get(_vigencia_key(placa=placa, documento=documento, tipo_documento=tipo_documento))

    def save_vigencia(
        self,
        *,
        placa: str,
        documento: str,
        tipo_documento: str,
        payload: dict[str, object],
    ) -> VehicleCacheRecord:
        cache_key = _vigencia_key(placa=placa, documento=documento, tipo_documento=tipo_documento)
        with self._lock:
            record = VehicleCacheRecord(cache_key=cache_key, payload=dict(payload))
            self._vigencia[cache_key] = record
            return record

    def get_multas(self, *, documento: str) -> VehicleCacheRecord | None:
        return self._multas.get(_multas_key(documento=documento))

    def save_multas(self, *, documento: str, payload: dict[str, object]) -> VehicleCacheRecord:
        cache_key = _multas_key(documento=documento)
        with self._lock:
            record = VehicleCacheRecord(cache_key=cache_key, payload=dict(payload))
            self._multas[cache_key] = record
            return record


def repository_from_env() -> VehicleCacheRepository:
    mode = os.getenv("VEHICLE_CACHE_MODE", "memory").strip().lower()
    if mode in {"", "memory"}:
        return InMemoryVehicleCacheRepository()
    if mode == "sql":
        database_url = os.getenv("VEHICLE_DATABASE_URL", "").strip()
        if not database_url:
            raise RuntimeError("VEHICLE_DATABASE_URL is required when VEHICLE_CACHE_MODE=sql")
        from vehicle_service.adapters.outbound.sql_cache_repository import SqlVehicleCacheRepository

        auto_create = os.getenv("VEHICLE_AUTO_CREATE_SCHEMA", "").strip().lower() in {"1", "true", "yes"}
        return SqlVehicleCacheRepository(database_url, create_schema=auto_create)
    raise RuntimeError(f"unsupported vehicle cache mode: {mode}")


def document_hash(value: str) -> str:
    return sha256(str(value or "").strip().encode("utf-8")).hexdigest()


def document_tail(value: str) -> str:
    raw = str(value or "").strip()
    return "****" if len(raw) <= 4 else f"****{raw[-4:]}"


def _vigencia_key(*, placa: str, documento: str, tipo_documento: str) -> str:
    normalized = f"{placa.strip().upper()}:{tipo_documento.strip().upper()}:{document_hash(documento)}"
    return sha256(normalized.encode("utf-8")).hexdigest()


def _multas_key(*, documento: str) -> str:
    return sha256(f"multas:{document_hash(documento)}".encode("utf-8")).hexdigest()


repository = repository_from_env()
