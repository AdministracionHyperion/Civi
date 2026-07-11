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
    def __init__(
        self,
        *,
        e164: str | None = "573009998877",
        bookable: bool = True,
        exists: bool = True,
    ) -> None:
        self.e164 = e164
        self.bookable = bookable
        self.exists = exists
        self.calls: list[str] = []

    async def get_ops_contact(self, site_id: str) -> dict[str, object] | None:
        if self.e164 is None:
            return None
        return {"site_id": site_id, "name": "CDA Centro", "e164": self.e164}

    async def booking_eligibility(self, site_id: str) -> dict[str, object]:
        self.calls.append(site_id)
        if not self.exists:
            return {
                "site_id": site_id,
                "exists": False,
                "is_partner": False,
                "is_bookable": False,
                "booking_mode": "unavailable",
                "operational_status": "unknown",
                "eligible_for_civi_booking": False,
                "eligibility_reason": "place_not_found",
            }
        return {
            "site_id": site_id,
            "exists": True,
            "is_partner": True,
            "is_bookable": self.bookable,
            "booking_mode": "civi" if self.bookable else "information_only",
            "operational_status": "unknown",
            "eligible_for_civi_booking": self.bookable,
            "eligibility_reason": "eligible" if self.bookable else "not_bookable",
            "source_presence_status": "present",
            "present_in_latest_snapshot": True,
            "canonical_name": "CDA Centro Bucaramanga",
            "canonical_address": "Calle 36 # 15-20",
            "canonical_city": "Bucaramanga",
        }


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


# Backward-compatible alias used by eligibility-focused tests.
FakePlacesEligibilityClient = FakePlacesClient


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
    assert any("12/07/2026 a las 11:00 a. m." in str(m["body"]) for m in fake_client.whatsapp)
    assert not any("2026-07-12T11:00" in str(m["body"]) for m in fake_client.whatsapp if "confirmada" in str(m["body"]).lower())
    assert len(fake_client.reminders) == 2


def test_format_starts_at_human() -> None:
    from appointment_service.shared.reminders import format_starts_at_human

    assert format_starts_at_human("2026-07-12T14:00") == "12/07/2026 a las 2:00 p. m."
    assert format_starts_at_human("2026-07-12T09:30") == "12/07/2026 a las 9:30 a. m."
    assert format_starts_at_human("not-a-date") == "not-a-date"


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


@pytest.mark.asyncio
async def test_create_appointment_rejects_non_bookable_place() -> None:
    from fastapi import HTTPException

    with pytest.raises(HTTPException) as exc:
        await create_appointment(
            CreateAppointmentRequest(
                user_key="user-nobook",
                procedure="tecnomecanica",
                starts_at="2026-07-14T09:00",
                place=AppointmentPlace(
                    id="info-only-01",
                    name="CDA Informativo",
                    address="Calle 1",
                    city="Bogota",
                ),
            ),
            places_client=FakePlacesEligibilityClient(bookable=False),
        )
    assert exc.value.status_code == 422
    assert exc.value.detail in {"place_not_bookable", "not_bookable"}


@pytest.mark.asyncio
async def test_create_appointment_returns_404_when_place_does_not_exist() -> None:
    from fastapi import HTTPException

    with pytest.raises(HTTPException) as exc:
        await create_appointment(
            CreateAppointmentRequest(
                user_key="user-missing-place",
                procedure="tecnomecanica",
                starts_at="2026-07-16T09:00",
                place=AppointmentPlace(
                    id="does-not-exist",
                    name="Fantasma",
                    address="N/A",
                    city="N/A",
                ),
            ),
            places_client=FakePlacesEligibilityClient(exists=False),
        )
    assert exc.value.status_code == 404
    assert exc.value.detail == "place_not_found"


@pytest.mark.asyncio
async def test_create_appointment_returns_503_when_places_catalog_unavailable() -> None:
    from fastapi import HTTPException

    from appointment_service.adapters.outbound.places_client import PlacesCatalogUnavailable

    class UnavailablePlacesClient:
        async def booking_eligibility(self, site_id: str) -> dict[str, object]:
            raise PlacesCatalogUnavailable("places_catalog_timeout")

        async def get_ops_contact(self, site_id: str) -> dict[str, object] | None:
            raise PlacesCatalogUnavailable("places_catalog_timeout")

    with pytest.raises(HTTPException) as exc:
        await create_appointment(
            CreateAppointmentRequest(
                user_key="user-places-down",
                procedure="tecnomecanica",
                starts_at="2026-07-17T09:00",
                place=AppointmentPlace(
                    id="bga-cda-centro-01",
                    name="CDA Centro Bucaramanga",
                    address="Calle 36 # 15-20",
                    city="Bucaramanga",
                ),
            ),
            places_client=UnavailablePlacesClient(),
        )
    assert exc.value.status_code == 503
    assert exc.value.detail == "places_catalog_unavailable"


@pytest.mark.asyncio
async def test_places_client_maps_timeout_and_500_to_catalog_unavailable(monkeypatch: pytest.MonkeyPatch) -> None:
    """PlacesClient must surface timeout/5xx as PlacesCatalogUnavailable (no silent 422)."""
    import httpx

    from appointment_service.adapters.outbound.places_client import PlacesCatalogUnavailable, PlacesClient

    class TimeoutTransport(httpx.AsyncBaseTransport):
        async def handle_async_request(self, request: httpx.Request) -> httpx.Response:
            raise httpx.ReadTimeout("timed out")

    class ServerErrorTransport(httpx.AsyncBaseTransport):
        async def handle_async_request(self, request: httpx.Request) -> httpx.Response:
            return httpx.Response(500, json={"detail": "boom"})

    async def _with_transport(transport: httpx.AsyncBaseTransport, site_id: str) -> None:
        original = httpx.AsyncClient

        class PatchedClient(original):
            def __init__(self, *args, **kwargs):
                kwargs["transport"] = transport
                super().__init__(*args, **kwargs)

        monkeypatch.setattr(httpx, "AsyncClient", PatchedClient)
        client = PlacesClient(base_url="http://places.test", token="t")
        with pytest.raises(PlacesCatalogUnavailable):
            await client.booking_eligibility(site_id)

    await _with_transport(TimeoutTransport(), "site-timeout")
    await _with_transport(ServerErrorTransport(), "site-500")


@pytest.mark.asyncio
async def test_create_appointment_persists_canonical_place_fields() -> None:
    created = await create_appointment(
        CreateAppointmentRequest(
            user_key="user-canonical",
            procedure="tecnomecanica",
            starts_at="2026-07-15T09:00",
            place=AppointmentPlace(
                id="bga-cda-centro-01",
                name="Nombre Cliente Mentiroso",
                address="Direccion Falsa",
                city="Ciudad Falsa",
            ),
        ),
        places_client=FakePlacesEligibilityClient(bookable=True),
    )
    assert created.appointment["place"]["name"] == "CDA Centro Bucaramanga"
    assert created.appointment["place"]["address"] == "Calle 36 # 15-20"
    assert created.appointment["place"]["city"] == "Bucaramanga"
