import pytest
from civi_common.events import InMemoryEventPublisher
from fastapi.testclient import TestClient

from appointment_service.main import app
from appointment_service.adapters.outbound.sql_repository import SqlAppointmentRepository
from appointment_service.slices.cancel_appointment.use_case import cancel_appointment
from appointment_service.slices.create_appointment.schemas import (
    AppointmentPlace,
    CreateAppointmentRequest,
)
from appointment_service.slices.create_appointment.use_case import create_appointment
from appointment_service.slices.list_appointments.use_case import list_appointments


class FakeNotificationClient:
    def __init__(self) -> None:
        self.calls: list[dict[str, object]] = []

    async def schedule_reminder(self, **payload: object) -> dict[str, object]:
        self.calls.append(payload)
        return {"reminder": {"id": 42, "to_tail": "****2233"}}


@pytest.mark.asyncio
async def test_create_list_cancel_appointment() -> None:
    created = await create_appointment(
        CreateAppointmentRequest(
            user_key="user-1",
            procedure="tecnomecanica",
            starts_at="2026-07-10T09:00",
            place=AppointmentPlace(
                id="bga-cda-centro-01",
                name="CDA Centro Bucaramanga",
                address="Bucaramanga, Santander",
                city="Bucaramanga",
            ),
        )
    )

    appointment_id = int(created.appointment["id"])
    listed = await list_appointments(user_key="user-1")
    assert len(listed.appointments) == 1

    cancelled = await cancel_appointment(user_key="user-1", appointment_id=appointment_id)
    assert cancelled.success

    listed_after_cancel = await list_appointments(user_key="user-1")
    assert listed_after_cancel.appointments == []


@pytest.mark.asyncio
async def test_create_appointment_schedules_notification_when_destination_exists() -> None:
    fake_client = FakeNotificationClient()
    publisher = InMemoryEventPublisher()

    created = await create_appointment(
        CreateAppointmentRequest(
            user_key="user-2",
            procedure="soat",
            starts_at="2026-07-11T10:00",
            notification_to="573001112233",
            place=AppointmentPlace(
                id="bga-cda-centro-01",
                name="CDA Centro Bucaramanga",
                address="Bucaramanga, Santander",
                city="Bucaramanga",
            ),
        ),
        notification_client=fake_client,
        event_publisher=publisher,
    )

    assert created.notification == {"status": "scheduled", "reminder_id": 42, "to_tail": "****2233"}
    assert fake_client.calls[0]["to"] == "573001112233"
    assert fake_client.calls[0]["remind_at"] == "2026-07-11T10:00"
    assert publisher.events[0]["event_type"] == "appointment.created"
    assert publisher.events[0]["producer"] == "appointment-service"
    assert publisher.events[0]["procedure"] == "soat"


@pytest.mark.asyncio
async def test_cancel_appointment_publishes_cancelled_event() -> None:
    publisher = InMemoryEventPublisher()
    created = await create_appointment(
        CreateAppointmentRequest(
            user_key="user-cancel-event",
            procedure="tecnomecanica",
            starts_at="2026-07-13T12:00",
            place=AppointmentPlace(
                id="bga-cda-centro-01",
                name="CDA Centro Bucaramanga",
                address="Bucaramanga, Santander",
                city="Bucaramanga",
            ),
        )
    )

    cancelled = await cancel_appointment(
        user_key="user-cancel-event",
        appointment_id=int(created.appointment["id"]),
        event_publisher=publisher,
    )

    assert cancelled.success
    assert publisher.events[0]["event_type"] == "appointment.cancelled"
    assert publisher.events[0]["producer"] == "appointment-service"
    assert publisher.events[0]["user_key"] == "user-cancel-event"


def test_sql_appointment_repository_persists_and_cancels() -> None:
    repo = SqlAppointmentRepository("sqlite+pysqlite:///:memory:", create_schema=True)

    record = repo.create(
        user_key="user-sql",
        procedure="tecnomecanica",
        starts_at="2026-07-12T11:00",
        place_id="bga-cda-centro-01",
        place_name="CDA Centro Bucaramanga",
        place_address="Bucaramanga, Santander",
        place_city="Bucaramanga",
    )

    assert repo.list_for_user(user_key="user-sql")[0].id == record.id
    cancelled = repo.cancel(user_key="user-sql", appointment_id=record.id)
    assert cancelled is not None
    assert cancelled.status == "cancelled"
    assert repo.list_for_user(user_key="user-sql") == []


def test_appointment_internal_status_requires_token(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("INTERNAL_SERVICE_TOKEN", "internal-test-token")
    client = TestClient(app)

    assert client.get("/internal/status").status_code == 401

    response = client.get(
        "/internal/status",
        headers={"Authorization": "Bearer internal-test-token"},
    )
    assert response.status_code == 200
    assert response.json()["service"] == "appointment-service"
