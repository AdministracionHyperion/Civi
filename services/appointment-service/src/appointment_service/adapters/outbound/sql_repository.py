from __future__ import annotations

from datetime import UTC, datetime

from sqlalchemy import Column, Integer, MetaData, String, Table, create_engine, inspect, select, text, update
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
    Column("partner_notified_at", String(64), nullable=True),
    Column("partner_confirmed_at", String(64), nullable=True),
    Column("client_notification_to", String(32), nullable=True),
    Column("partner_notification_to", String(32), nullable=True),
)

_EXTRA_COLUMNS = (
    ("partner_notified_at", "VARCHAR(64)"),
    ("partner_confirmed_at", "VARCHAR(64)"),
    ("client_notification_to", "VARCHAR(32)"),
    ("partner_notification_to", "VARCHAR(32)"),
)


def _ensure_schema(engine: Engine) -> None:
    metadata.create_all(engine)
    inspector = inspect(engine)
    if "appointments" not in inspector.get_table_names():
        return
    existing = {col["name"] for col in inspector.get_columns("appointments")}
    with engine.begin() as conn:
        for name, col_type in _EXTRA_COLUMNS:
            if name not in existing:
                conn.execute(text(f"ALTER TABLE appointments ADD COLUMN {name} {col_type}"))


class SqlAppointmentRepository:
    def __init__(self, database_url: str, *, create_schema: bool = False) -> None:
        self.engine: Engine = create_engine(database_url, future=True)
        if create_schema:
            _ensure_schema(self.engine)

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
        status: str = "pending_partner",
        client_notification_to: str | None = None,
        partner_notification_to: str | None = None,
        partner_notified_at: str | None = None,
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
                    status=status,
                    created_at=created_at,
                    partner_notified_at=partner_notified_at,
                    partner_confirmed_at=None,
                    client_notification_to=client_notification_to,
                    partner_notification_to=partner_notification_to,
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
            status=status,
            created_at=created_at,
            partner_notified_at=partner_notified_at,
            client_notification_to=client_notification_to,
            partner_notification_to=partner_notification_to,
        )

    def get(self, *, appointment_id: int) -> AppointmentRecord | None:
        with self.engine.begin() as conn:
            row = conn.execute(
                select(appointments).where(appointments.c.id == appointment_id)
            ).mappings().first()
        return _record_from_row(row) if row else None

    def list_for_user(self, *, user_key: str) -> list[AppointmentRecord]:
        stmt = (
            select(appointments)
            .where(appointments.c.user_key == user_key)
            .where(appointments.c.status.notin_(["cancelled", "rejected"]))
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

    def confirm(self, *, appointment_id: int) -> AppointmentRecord | None:
        confirmed_at = datetime.now(UTC).isoformat(timespec="seconds")
        with self.engine.begin() as conn:
            row = conn.execute(
                select(appointments)
                .where(appointments.c.id == appointment_id)
                .where(appointments.c.status == "pending_partner")
            ).mappings().first()
            if row is None:
                return None
            conn.execute(
                update(appointments)
                .where(appointments.c.id == appointment_id)
                .values(status="confirmed", partner_confirmed_at=confirmed_at)
            )
        record = _record_from_row(row)
        record.status = "confirmed"
        record.partner_confirmed_at = confirmed_at
        return record

    def reject(self, *, appointment_id: int) -> AppointmentRecord | None:
        rejected_at = datetime.now(UTC).isoformat(timespec="seconds")
        with self.engine.begin() as conn:
            row = conn.execute(
                select(appointments)
                .where(appointments.c.id == appointment_id)
                .where(appointments.c.status == "pending_partner")
            ).mappings().first()
            if row is None:
                return None
            conn.execute(
                update(appointments)
                .where(appointments.c.id == appointment_id)
                .values(status="rejected", partner_confirmed_at=rejected_at)
            )
        record = _record_from_row(row)
        record.status = "rejected"
        record.partner_confirmed_at = rejected_at
        return record

    def mark_partner_notified(self, *, appointment_id: int, notified_at: str) -> AppointmentRecord | None:
        with self.engine.begin() as conn:
            row = conn.execute(
                select(appointments).where(appointments.c.id == appointment_id)
            ).mappings().first()
            if row is None:
                return None
            conn.execute(
                update(appointments)
                .where(appointments.c.id == appointment_id)
                .values(partner_notified_at=notified_at)
            )
        record = _record_from_row(row)
        record.partner_notified_at = notified_at
        return record


def _record_from_row(row) -> AppointmentRecord:
    keys = row.keys()
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
        partner_notified_at=str(row["partner_notified_at"]) if "partner_notified_at" in keys and row.get("partner_notified_at") else None,
        partner_confirmed_at=str(row["partner_confirmed_at"]) if "partner_confirmed_at" in keys and row.get("partner_confirmed_at") else None,
        client_notification_to=str(row["client_notification_to"]) if "client_notification_to" in keys and row.get("client_notification_to") else None,
        partner_notification_to=str(row["partner_notification_to"]) if "partner_notification_to" in keys and row.get("partner_notification_to") else None,
    )
