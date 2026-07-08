from __future__ import annotations

from datetime import UTC, datetime

from sqlalchemy import Column, Integer, MetaData, String, Table, create_engine, select, update
from sqlalchemy.engine import Engine

from appointment_service.shared.repository import AppointmentRecord

metadata = MetaData()

appointments = Table(
    "appointments",
    metadata,
    Column("id", Integer, primary_key=True, autoincrement=True),
    Column("user_key", String(128), nullable=False, index=True),
    Column("procedure", String(64), nullable=False),
    Column("place_id", String(128), nullable=False),
    Column("place_name", String(256), nullable=False),
    Column("place_address", String(512), nullable=False),
    Column("place_city", String(128), nullable=False),
    Column("starts_at", String(64), nullable=False, index=True),
    Column("status", String(32), nullable=False),
    Column("created_at", String(64), nullable=False),
)


class SqlAppointmentRepository:
    def __init__(self, database_url: str, *, create_schema: bool = False) -> None:
        self.engine: Engine = create_engine(database_url, future=True)
        if create_schema:
            metadata.create_all(self.engine)

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
        created_at = datetime.now(UTC).isoformat(timespec="seconds")
        with self.engine.begin() as conn:
            result = conn.execute(
                appointments.insert().values(
                    user_key=user_key,
                    procedure=procedure,
                    place_id=place_id,
                    place_name=place_name,
                    place_address=place_address,
                    place_city=place_city,
                    starts_at=starts_at,
                    status="scheduled",
                    created_at=created_at,
                )
            )
            record_id = int(result.inserted_primary_key[0])
        return AppointmentRecord(
            id=record_id,
            user_key=user_key,
            procedure=procedure,
            place_id=place_id,
            place_name=place_name,
            place_address=place_address,
            place_city=place_city,
            starts_at=starts_at,
            status="scheduled",
            created_at=created_at,
        )

    def list_for_user(self, *, user_key: str) -> list[AppointmentRecord]:
        stmt = (
            select(appointments)
            .where(appointments.c.user_key == user_key)
            .where(appointments.c.status != "cancelled")
            .order_by(appointments.c.starts_at)
        )
        with self.engine.begin() as conn:
            rows = conn.execute(stmt).mappings().all()
        return [_record_from_row(row) for row in rows]

    def cancel(self, *, user_key: str, appointment_id: int) -> AppointmentRecord | None:
        with self.engine.begin() as conn:
            row = conn.execute(
                select(appointments)
                .where(appointments.c.id == appointment_id)
                .where(appointments.c.user_key == user_key)
                .where(appointments.c.status != "cancelled")
            ).mappings().first()
            if row is None:
                return None
            conn.execute(
                update(appointments)
                .where(appointments.c.id == appointment_id)
                .values(status="cancelled")
            )
        record = _record_from_row(row)
        record.status = "cancelled"
        return record


def _record_from_row(row) -> AppointmentRecord:
    return AppointmentRecord(
        id=int(row["id"]),
        user_key=str(row["user_key"]),
        procedure=str(row["procedure"]),
        place_id=str(row["place_id"]),
        place_name=str(row["place_name"]),
        place_address=str(row["place_address"]),
        place_city=str(row["place_city"]),
        starts_at=str(row["starts_at"]),
        status=str(row["status"]),
        created_at=str(row["created_at"]),
    )
