from __future__ import annotations

import pytest

from appointment_service.shared.repository import InMemoryAppointmentRepository
from appointment_service.slices.create_appointment.schemas import CreateAppointmentRequest
from civi_common.events import InMemoryEventPublisher
from channel_gateway.slices.receive_message.schemas import ReceiveMessageRequest
from channel_gateway.slices.receive_message.use_case import receive_message
from conversation_service.shared.repository import InMemoryConversationRepository
from conversation_service.slices.run_turn.schemas import RunTurnRequest
from conversation_service.slices.run_turn.use_case import run_turn
import bot_orchestrator.slices.run_turn.use_case as agent_use_case
from bot_orchestrator.slices.run_turn.schemas import AgentTurnRequest
from notification_service.shared.repository import InMemoryNotificationRepository
from notification_service.slices.process_due_reminders.use_case import process_due_reminders
from notification_service.slices.schedule_reminder.schemas import ScheduleReminderRequest

import appointment_service.slices.create_appointment.use_case as appointment_use_case
import notification_service.slices.schedule_reminder.use_case as schedule_reminder_use_case


class FakeLLMProvider:
    async def complete(
        self,
        *,
        system_prompt: str,
        user_text: str,
        user_key: str,
        channel: str,
    ) -> dict[str, object]:
        return {"provider_mode": "offline-llm", "text": f"respuesta offline LLM para {user_text}"}


class FakeVehicleClient:
    async def check_vigencia(
        self,
        *,
        placa: str,
        documento: str,
        tipo_documento: str = "CC",
    ) -> dict[str, object]:
        return {
            "placa": placa,
            "vehiculo": {"marca": "Mazda", "linea": "2", "modelo": 2020},
            "soat": {"fechaVencimiento": "2026-10-15", "diasRestantes": 100},
            "rtm": {"fechaVencimiento": "2026-11-20", "diasRestantes": 136},
        }

    async def consult_multas(self, *, documento: str) -> dict[str, object]:
        return {"tieneMultas": False}


class FakePlacesClient:
    async def find_nearest(
        self,
        *,
        procedure: str,
        city: str | None = None,
        lat: float | None = None,
        lng: float | None = None,
    ) -> dict[str, object]:
        return {
            "places": [
                {
                    "id": "cda-bga-1",
                    "name": "CDA Bucaramanga",
                    "address": "Cra 1 # 2-3",
                    "city": city or "Bucaramanga",
                    "department": "Santander",
                    "kind": "CDA",
                    "distance_km": 2.5,
                    "is_bookable": True,
                    "booking_mode": "civi",
                    "is_partner": True,
                }
            ]
        }


class FakePlacesEligibilityClient:
    async def booking_eligibility(self, site_id: str) -> dict[str, object]:
        return {
            "site_id": site_id,
            "exists": True,
            "is_partner": True,
            "is_bookable": True,
            "booking_mode": "civi",
            "operational_status": "unknown",
            "eligible_for_civi_booking": True,
            "eligibility_reason": "eligible",
            "source_presence_status": "present",
            "present_in_latest_snapshot": True,
            "canonical_name": "CDA Bucaramanga",
            "canonical_address": "Cra 1 # 2-3",
            "canonical_city": "Bucaramanga",
        }


class LocalReminderClient:
    def __init__(self, *, event_publisher: InMemoryEventPublisher) -> None:
        self._event_publisher = event_publisher

    async def schedule_reminder(
        self,
        *,
        user_key: str,
        to: str,
        body: str,
        remind_at: str,
    ) -> dict[str, object]:
        response = await schedule_reminder_use_case.schedule_reminder(
            ScheduleReminderRequest(user_key=user_key, to=to, body=body, remind_at=remind_at),
            event_publisher=self._event_publisher,
        )
        return response.model_dump()


class LocalAppointmentClient:
    def __init__(self, *, event_publisher: InMemoryEventPublisher) -> None:
        self._event_publisher = event_publisher

    async def create(
        self,
        *,
        user_key: str,
        procedure: str,
        starts_at: str,
        place: dict[str, object],
        notification_to: str | None = None,
    ) -> dict[str, object]:
        response = await appointment_use_case.create_appointment(
            CreateAppointmentRequest(
                user_key=user_key,
                procedure=procedure,
                starts_at=starts_at,
                place=place,
                notification_to=notification_to,
            ),
            notification_client=LocalReminderClient(event_publisher=self._event_publisher),
            event_publisher=self._event_publisher,
            places_client=FakePlacesEligibilityClient(),
        )
        return response.model_dump()

    async def list_for_user(self, *, user_key: str) -> dict[str, object]:
        records = appointment_use_case.repository.list_for_user(user_key=user_key)
        return {
            "appointments": [
                {
                    "id": record.id,
                    "starts_at": record.starts_at,
                    "place": {"name": record.place_name},
                }
                for record in records
            ]
        }


class OfflineAgentClient:
    def __init__(self, *, event_publisher: InMemoryEventPublisher) -> None:
        self.calls = 0
        self._event_publisher = event_publisher

    async def run_turn(self, payload: RunTurnRequest) -> dict[str, object]:
        self.calls += 1
        original_appointment_client = agent_use_case.AppointmentClient
        agent_use_case.AppointmentClient = lambda: LocalAppointmentClient(event_publisher=self._event_publisher)
        try:
            response = await agent_use_case.run_agent_turn(
                AgentTurnRequest(user_key=payload.user_key, text=payload.text, channel=payload.channel),
                llm_provider=FakeLLMProvider(),
            )
        finally:
            agent_use_case.AppointmentClient = original_appointment_client
        return response.model_dump()


class OfflineConversationClient:
    def __init__(
        self,
        *,
        repository: InMemoryConversationRepository,
        event_publisher: InMemoryEventPublisher,
        agent_client: OfflineAgentClient,
    ) -> None:
        self._repository = repository
        self._event_publisher = event_publisher
        self._agent_client = agent_client

    async def run_turn(self, payload: ReceiveMessageRequest) -> dict[str, object]:
        response = await run_turn(
            RunTurnRequest(user_key=payload.user_key, text=payload.text, channel=payload.channel),
            agent_client=self._agent_client,
            conversation_repository=self._repository,
            event_publisher=self._event_publisher,
        )
        return response.model_dump()


@pytest.mark.asyncio
async def test_offline_core_conversation_flow(monkeypatch: pytest.MonkeyPatch) -> None:
    event_publisher = InMemoryEventPublisher()
    conversation_repository = InMemoryConversationRepository()
    appointment_repository = InMemoryAppointmentRepository()
    notification_repository = InMemoryNotificationRepository()

    monkeypatch.setattr(agent_use_case, "VehicleClient", FakeVehicleClient)
    monkeypatch.setattr(agent_use_case, "PlacesClient", FakePlacesClient)
    monkeypatch.setattr(appointment_use_case, "repository", appointment_repository)
    monkeypatch.setattr(schedule_reminder_use_case, "repository", notification_repository)

    agent_client = OfflineAgentClient(event_publisher=event_publisher)
    conversation_client = OfflineConversationClient(
        repository=conversation_repository,
        event_publisher=event_publisher,
        agent_client=agent_client,
    )

    pending = await receive_message(
        ReceiveMessageRequest(
            user_key="573001112233",
            text="mi cedula es 123456789",
            channel="whatsapp",
        ),
        conversation_client=conversation_client,
        event_publisher=event_publisher,
    )
    assert "autorizacion" in pending.text
    assert agent_client.calls == 0
    assert conversation_repository.list_for_user(user_key="573001112233")[0].user_text == (
        "[consent_pending_message_redacted]"
    )

    accepted = await receive_message(
        ReceiveMessageRequest(user_key="573001112233", text="acepto", channel="whatsapp"),
        conversation_client=conversation_client,
        event_publisher=event_publisher,
    )
    assert "consentimiento" in accepted.text
    assert conversation_repository.get_consent(user_key="573001112233", channel="whatsapp").status == "accepted"
    assert agent_client.calls == 0

    fallback = await receive_message(
        ReceiveMessageRequest(user_key="573001112233", text="explicame que puedes hacer", channel="whatsapp"),
        conversation_client=conversation_client,
        event_publisher=event_publisher,
    )
    assert fallback.text == "respuesta offline LLM para explicame que puedes hacer"

    vehicle = await receive_message(
        ReceiveMessageRequest(
            user_key="573001112233",
            text="consulta soat de ABC123 cedula 123456789",
            channel="whatsapp",
        ),
        conversation_client=conversation_client,
        event_publisher=event_publisher,
    )
    assert "SOAT vigente hasta el *15/10/2026*" in vehicle.text

    appointment = await receive_message(
        ReceiveMessageRequest(
            user_key="573001112233",
            text="quiero agendar tecnomecanica en Bucaramanga el 2026-07-10 09:00",
            channel="whatsapp",
        ),
        conversation_client=conversation_client,
        event_publisher=event_publisher,
    )
    assert "Listo, cita creada" in appointment.text
    assert appointment_repository.list_for_user(user_key="573001112233")
    assert notification_repository.list_reminders(user_key="573001112233")

    due = await process_due_reminders(
        now="2026-07-10T09:00",
        notification_repository=notification_repository,
        event_publisher=event_publisher,
    )
    assert due.count == 1
    assert notification_repository.list_queued()[0].status == "queued"

    event_types = [event["event_type"] for event in event_publisher.events]
    assert event_types.count("message.received") == 5
    assert "consent.updated" in event_types
    assert "conversation.completed" in event_types
    assert "appointment.created" in event_types
    assert "reminder.scheduled" in event_types
    assert "reminder.due" in event_types
    assert "notification.queued" in event_types
