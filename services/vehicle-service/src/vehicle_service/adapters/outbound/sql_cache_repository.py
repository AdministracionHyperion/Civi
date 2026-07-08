from __future__ import annotations

import json
from datetime import UTC, datetime

from sqlalchemy import Column, MetaData, String, Table, create_engine, select
from sqlalchemy.dialects.sqlite import insert as sqlite_insert
from sqlalchemy.engine import Engine

from vehicle_service.shared.cache_repository import (
    VehicleCacheRecord,
    document_hash,
    document_tail,
)

metadata = MetaData()

vehicle_vigencia_cache = Table(
    "vehicle_vigencia_cache",
    metadata,
    Column("cache_key", String(128), primary_key=True),
    Column("placa", String(16), nullable=False, index=True),
    Column("tipo_documento", String(16), nullable=False),
    Column("documento_hash", String(128), nullable=False, index=True),
    Column("documento_tail", String(16), nullable=False),
    Column("payload_json", String, nullable=False),
    Column("created_at", String(64), nullable=False),
)

vehicle_multas_cache = Table(
    "vehicle_multas_cache",
    metadata,
    Column("cache_key", String(128), primary_key=True),
    Column("documento_hash", String(128), nullable=False, index=True),
    Column("documento_tail", String(16), nullable=False),
    Column("payload_json", String, nullable=False),
    Column("created_at", String(64), nullable=False),
)


class SqlVehicleCacheRepository:
    def __init__(self, database_url: str, *, create_schema: bool = False) -> None:
        self.engine: Engine = create_engine(database_url, future=True)
        if create_schema:
            metadata.create_all(self.engine)

    def get_vigencia(self, *, placa: str, documento: str, tipo_documento: str) -> VehicleCacheRecord | None:
        cache_key = _vigencia_key(placa=placa, documento=documento, tipo_documento=tipo_documento)
        with self.engine.begin() as conn:
            row = conn.execute(
                select(vehicle_vigencia_cache).where(vehicle_vigencia_cache.c.cache_key == cache_key)
            ).mappings().first()
        return _record_from_row(row) if row else None

    def save_vigencia(
        self,
        *,
        placa: str,
        documento: str,
        tipo_documento: str,
        payload: dict[str, object],
    ) -> VehicleCacheRecord:
        cache_key = _vigencia_key(placa=placa, documento=documento, tipo_documento=tipo_documento)
        created_at = datetime.now(UTC).isoformat(timespec="seconds")
        values = {
            "cache_key": cache_key,
            "placa": placa.strip().upper(),
            "tipo_documento": tipo_documento.strip().upper(),
            "documento_hash": document_hash(documento),
            "documento_tail": document_tail(documento),
            "payload_json": json.dumps(payload, sort_keys=True, separators=(",", ":")),
            "created_at": created_at,
        }
        _upsert(self.engine, vehicle_vigencia_cache, values)
        return VehicleCacheRecord(cache_key=cache_key, payload=dict(payload), created_at=created_at)

    def get_multas(self, *, documento: str) -> VehicleCacheRecord | None:
        cache_key = _multas_key(documento=documento)
        with self.engine.begin() as conn:
            row = conn.execute(
                select(vehicle_multas_cache).where(vehicle_multas_cache.c.cache_key == cache_key)
            ).mappings().first()
        return _record_from_row(row) if row else None

    def save_multas(self, *, documento: str, payload: dict[str, object]) -> VehicleCacheRecord:
        cache_key = _multas_key(documento=documento)
        created_at = datetime.now(UTC).isoformat(timespec="seconds")
        values = {
            "cache_key": cache_key,
            "documento_hash": document_hash(documento),
            "documento_tail": document_tail(documento),
            "payload_json": json.dumps(payload, sort_keys=True, separators=(",", ":")),
            "created_at": created_at,
        }
        _upsert(self.engine, vehicle_multas_cache, values)
        return VehicleCacheRecord(cache_key=cache_key, payload=dict(payload), created_at=created_at)


def _upsert(engine: Engine, table: Table, values: dict[str, object]) -> None:
    with engine.begin() as conn:
        if engine.dialect.name == "sqlite":
            stmt = sqlite_insert(table).values(**values)
            conn.execute(stmt.on_conflict_do_update(index_elements=["cache_key"], set_=values))
            return
        existing = conn.execute(select(table.c.cache_key).where(table.c.cache_key == values["cache_key"])).first()
        if existing is not None:
            conn.execute(table.update().where(table.c.cache_key == values["cache_key"]).values(**values))
        else:
            conn.execute(table.insert().values(**values))


def _record_from_row(row) -> VehicleCacheRecord:
    return VehicleCacheRecord(
        cache_key=str(row["cache_key"]),
        payload=json.loads(str(row["payload_json"])),
        created_at=str(row["created_at"]),
    )


def _vigencia_key(*, placa: str, documento: str, tipo_documento: str) -> str:
    from vehicle_service.shared.cache_repository import _vigencia_key as build_key

    return build_key(placa=placa, documento=documento, tipo_documento=tipo_documento)


def _multas_key(*, documento: str) -> str:
    from vehicle_service.shared.cache_repository import _multas_key as build_key

    return build_key(documento=documento)
