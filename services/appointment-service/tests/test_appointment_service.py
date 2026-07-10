import pytest
from civi_common.events import InMemoryEventPublisher
from fastapi import HTTPException
from fastapi.testclient import TestClient

from appointment_service.main import app
from appointment_service.adapters.outbound.sql_repository import SqlAppointmentRepository
from appointment_service.slices.cancel_appointment.use_case import cancel_appointment
from appointment_service.slices.confirm_appointment.use_case import confirm_appointment
from appointment_service.slices.create_appointment.schemas import (
    AppointmentPlace,
    CreateAppointmentRequest,
)
from appointment_service.slices.create_appointment.use_case import create_appointment
import appointment_service.slices.create_appointment.use_case as create_use_case
from appointment_service.slices.list_appointments.use_case import list_appointments
from appointment_service.slices.reject_appointment.use_case import reject_appointment
from appointment_service.shared.repository import InMemoryAppointmentRepository


class FakeNotificationClient:
    def __init__(self) -> None:
        self.whatsapp: list[dict[str, object]] = []
        self.reminders: list[dict[str, object]] = []

    async def send_whatsapp_message(self, *, to: str, body: str) -> dict[str, object]:
        self.whatsapp.append({"to": to, "body": body})
        return {"success": True, "message": {"id": 1}}

    async def schedule_reminder(self, **payload: object) -> dict[str, object]:
        self.reminders.append(payload)
        return {"reminder": {"id": 42 + len(self.reminders), "to_tail": "****2233"}}


class FakePlacesClient:
    def __init__(self, *, e164: str | None = "573009998877") -> None:
        self.e164 = e164

    async def get_ops_contact(self, site_id: str) -> dict[str, object] | None:
        if self.e164 is None:
            return None
        return {"site_id": site_id, "name": "CDA Centro", "e164": self.e164}


@pytest.fixture(autouse=True)
def _fresh_repo(monkeypatch: pytest.MonkeyPatch):
    repo = InMemoryAppointmentRepository()
    monkeypatch.setattr(create_use_case, "repository", repo)
    monkeypatch.setattr(
        "appointment_service.slices.confirm_appointment.use_case.repository",
        repo,
    )
    monkeypatch.setattr(
        "appointment_service.slices.reject_appointment.use_case.repository",
        repo,
    )
    monkeypatch.setattr(
        "appointment_service.slices.cancel_appointment.use_case.repository",
        repo,
    )
    monkeypatch.setattr(
        "appointment_service.slices.list_appointments.use_case.repository",
        repo,
    )
    return repo


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
            notification_to="573001112233",
        ),
        places_client=FakePlacesClient(),
        notification_client=FakeNotificationClient(),
    )

    appointment_id = int(created.appointment["id"])
    assert created.appointment["status"] == "pending_partner"
    listed = await list_appointments(user_key="user-1")
    assert len(listed.appointments) == 1

    cancelled = await cancel_appointment(user_key="user-1", appointment_id=appointment_id)
    assert cancelled.success

    listed_after_cancel = await list_appointments(user_key="user-1")
    assert listed_after_cancel.appointments == []


@pytest.mark.asyncio
async def test_create_notifies_partner_without_client_reminder() -> None:
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
        places_client=FakePlacesClient(),
        event_publisher=publisher,
    )

    assert created.appointment["status"] == "pending_partner"
    assert created.notification == {
        "status": "sent",
        "to": "573009998877",
        "kind": "partner_request",
    }
    assert len(fake_client.whatsapp) == 1
    assert "CONFIRMAR" in str(fake_client.whatsapp[0]["body"])
    assert fake_client.reminders == []
    assert publisher.events[0]["event_type"] == "appointment.created"


@pytest.mark.asyncio
async def test_create_without_ops_whatsapp_returns_422() -> None:
    with pytest.raises(HTTPException) as exc:
        await create_appointment(
            CreateAppointmentRequest(
                user_key="user-3",
                procedure="tecnomecanica",
                starts_at="2026-07-11T10:00",
                place=AppointmentPlace(
                    id="ghost",
                    name="Ghost",
                    address="X",
                    city="Bucaramanga",
                ),
            ),
            places_client=FakePlacesClient(e164=None),
            notification_client=FakeNotificationClient(),
        )
    assert exc.value.status_code == 422
    assert exc.value.detail == "place_not_notifiable"


@pytest.mark.asyncio
async def test_confirm_schedules_dual_reminders_and_notifies_client() -> None:
    fake_client = FakeNotificationClient()
    created = await create_appointment(
        CreateAppointmentRequest(
            user_key="user-4",
            procedure="tecnomecanica",
            starts_at="2026-07-12T11:00",
            notification_to="573001112233",
            place=AppointmentPlace(
                id="bga-cda-centro-01",
                name="CDA Centro Bucaramanga",
                address="Bucaramanga, Santander",
                city="Bucaramanga",
            ),
        ),
        places_client=FakePlacesClient(),
        notification_client=fake_client,
    )
    appointment_id = int(created.appointment["id"])
    confirmed = await confirm_appointment(
        appointment_id=appointment_id,
        notification_client=fake_client,
        event_publisher=InMemoryEventPublisher(),
    )
    assert confirmed.success
    assert confirmed.appointment["status"] == "confirmed"
    assert any("confirmada" in str(m["body"]).lower() for m in fake_client.whatsapp)
    assert len(fake_client.reminders) == 2


@pytest.mark.asyncio
async def test_reject_notifies_client() -> None:
    fake_client = FakeNotificationClient()
    created = await create_appointment(
        CreateAppointmentRequest(
            user_key="user-5",
            procedure="tecnomecanica",
            starts_at="2026-07-12T11:00",
            notification_to="573001112233",
            place=AppointmentPlace(
                id="bga-cda-centro-01",
                name="CDA Centro Bucaramanga",
                address="Bucaramanga, Santander",
                city="Bucaramanga",
            ),
        ),
        places_client=FakePlacesClient(),
        notification_client=fake_client,
    )
    rejected = await reject_appointment(
        appointment_id=int(created.appointment["id"]),
        notification_client=fake_client,
        event_publisher=InMemoryEventPublisher(),
    )
    assert rejected.success
    assert rejected.appointment["status"] == "rejected"
    assert any("no pudo confirmar" in str(m["body"]).lower() for m in fake_client.whatsapp)


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
            notification_to="573001112233",
        ),
        places_client=FakePlacesClient(),
        notification_client=FakeNotificationClient(),
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
        partner_notification_to="573009998877",
        client_notification_to="573001112233",
    )

    assert record.status == "pending_partner"
    assert repo.list_for_user(user_key="user-sql")[0].id == record.id
    confirmed = repo.confirm(appointment_id=record.id)
    assert confirmed is not None
    assert confirmed.status == "confirmed"
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
