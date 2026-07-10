import json

import pytest
import httpx
from civi_common.events import InMemoryEventPublisher
from fastapi.testclient import TestClient

from notification_service.adapters.outbound.whatsapp_provider import MetaWhatsAppProvider, whatsapp_provider_from_env
from notification_service.adapters.outbound.sql_repository import SqlNotificationRepository
from notification_service.main import app
from notification_service.slices.dispatch_outbox.use_case import dispatch_outbox
from notification_service.slices.process_due_reminders.use_case import process_due_reminders
from notification_service.slices.process_due_reminders.schemas import ProcessDueRemindersResponse
from notification_service.slices.schedule_reminder.schemas import ScheduleReminderRequest
from notification_service.slices.schedule_reminder.use_case import schedule_reminder
from notification_service.slices.send_whatsapp_message.schemas import SendWhatsAppMessageRequest
from notification_service.slices.send_whatsapp_message.use_case import send_whatsapp_message
from notification_service.shared.repository import InMemoryNotificationRepository
from notification_service.workers import reminders as reminder_worker


class FakeSentWhatsAppProvider:
    async def send(self, *, to: str, body: str) -> dict[str, object]:
        return {"status": "sent", "provider": "fake-whatsapp"}


def test_notification_internal_endpoint_requires_bearer(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("INTERNAL_SERVICE_TOKEN", "internal-test-token")

    client = TestClient(app)
    unauthorized = client.post(
        "/internal/notifications/whatsapp",
        json={"to": "573001112233", "body": "Prueba Civi"},
    )
    assert unauthorized.status_code == 401

    authorized = client.post(
        "/internal/notifications/whatsapp",
        json={"to": "573001112233", "body": "Prueba Civi"},
        headers={"Authorization": "Bearer internal-test-token"},
    )
    assert authorized.status_code == 202
    assert authorized.json()["message"]["to_tail"] == "****2233"


@pytest.mark.asyncio
async def test_queue_and_dispatch_whatsapp_message() -> None:
    publisher = InMemoryEventPublisher()
    queued = await send_whatsapp_message(
        SendWhatsAppMessageRequest(to="573001112233", body="Prueba Civi"),
        event_publisher=publisher,
    )

    assert queued.message["status"] == "queued"
    assert queued.message["to_tail"] == "****2233"
    assert queued.message["body_length"] == len("Prueba Civi")
    assert "body" not in queued.message
    assert publisher.events[0]["event_type"] == "notification.queued"
    assert publisher.events[0]["to_tail"] == "****2233"

    dispatched = await dispatch_outbox(provider=FakeSentWhatsAppProvider(), event_publisher=publisher)
    assert dispatched.dispatched
    assert dispatched.dispatched[-1]["status"] == "sent"
    assert "body" not in dispatched.dispatched[-1]
    assert any(
        event["event_type"] == "notification.sent"
        and event["message_id"] == queued.message["id"]
        and event["provider"] == "fake-whatsapp"
        for event in publisher.events
    )


@pytest.mark.asyncio
async def test_dispatch_outbox_default_provider_is_disabled() -> None:
    await send_whatsapp_message(SendWhatsAppMessageRequest(to="573001112244", body="No enviar aun"))

    dispatched = await dispatch_outbox()

    assert dispatched.dispatched
    assert dispatched.dispatched[-1]["dispatch_status"] == "disabled_until_provider_configured"
    # claim_queued_batch marks rows as sending before provider call; disabled provider does not mark_sent
    assert dispatched.dispatched[-1]["status"] == "sending"


def test_whatsapp_provider_mode_fails_closed(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("WHATSAPP_PROVIDER_MODE", "unknown-provider")

    with pytest.raises(RuntimeError, match="unsupported WhatsApp provider mode"):
        whatsapp_provider_from_env()


def test_meta_whatsapp_provider_requires_credentials(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("WHATSAPP_PROVIDER_MODE", "meta")
    monkeypatch.delenv("WHATSAPP_ACCESS_TOKEN", raising=False)
    monkeypatch.delenv("WHATSAPP_PHONE_NUMBER_ID", raising=False)

    with pytest.raises(RuntimeError, match="WHATSAPP_ACCESS_TOKEN"):
        whatsapp_provider_from_env()


@pytest.mark.asyncio
async def test_meta_whatsapp_provider_sends_expected_payload_without_live_call() -> None:
    requests: list[httpx.Request] = []

    async def handler(request: httpx.Request) -> httpx.Response:
        requests.append(request)
        return httpx.Response(200, json={"messages": [{"id": "wamid.test"}]})

    provider = MetaWhatsAppProvider(
        access_token="token-test",
        phone_number_id="phone-id-test",
        base_url="https://graph.example.test",
        transport=httpx.MockTransport(handler),
    )

    result = await provider.send(to="573001112233", body="Prueba Civi")

    assert result == {
        "status": "sent",
        "provider": "meta-whatsapp",
        "provider_message_id": "wamid.test",
    }
    assert str(requests[0].url) == "https://graph.example.test/v20.0/phone-id-test/messages"
    assert requests[0].headers["Authorization"] == "Bearer token-test"
    sent_payload = json.loads(requests[0].read().decode("utf-8"))
    assert sent_payload["messaging_product"] == "whatsapp"
    assert sent_payload["to"] == "573001112233"
    assert sent_payload["text"]["body"] == "Prueba Civi"


def test_sql_notification_repository_persists_outbox_and_reminders() -> None:
    repo = SqlNotificationRepository("sqlite+pysqlite:///:memory:", create_schema=True)

    queued = repo.queue_message(to="573001112233", body="Prueba Civi")
    assert repo.list_queued()[0].id == queued.id

    sent = repo.mark_sent(queued.id)
    assert sent is not None
    assert sent.status == "sent"
    assert repo.list_queued() == []

    reminder = repo.schedule_reminder(
        user_key="user-sql",
        to="573001112233",
        body="Recordatorio Civi",
        remind_at="2026-07-12T12:00",
    )
    assert repo.list_reminders(user_key="user-sql")[0].id == reminder.id


def test_sql_notification_repository_queues_due_reminder_once() -> None:
    repo = SqlNotificationRepository("sqlite+pysqlite:///:memory:", create_schema=True)
    due = repo.schedule_reminder(
        user_key="user-due-sql",
        to="573001112233",
        body="Recordatorio SQL",
        remind_at="2026-07-10T09:00",
    )
    repo.schedule_reminder(
        user_key="user-future-sql",
        to="573001112244",
        body="Recordatorio futuro",
        remind_at="2026-07-11T09:00",
    )

    assert [reminder.id for reminder in repo.list_due_reminders(now="2026-07-10T09:30")] == [due.id]
    queued = repo.queue_due_reminder(reminder_id=due.id)

    assert queued is not None
    queued_reminder, message = queued
    assert queued_reminder.status == "queued"
    assert message.status == "queued"
    assert repo.queue_due_reminder(reminder_id=due.id) is None
    assert repo.list_due_reminders(now="2026-07-10T09:30") == []


@pytest.mark.asyncio
async def test_schedule_reminder() -> None:
    publisher = InMemoryEventPublisher()
    scheduled = await schedule_reminder(
        ScheduleReminderRequest(
            user_key="user-1",
            to="573001112233",
            body="Recordatorio Civi",
            remind_at="2026-07-10T09:00",
        ),
        event_publisher=publisher,
    )

    assert scheduled.reminder["status"] == "scheduled"
    assert scheduled.reminder["to_tail"] == "****2233"
    assert scheduled.reminder["body_length"] == len("Recordatorio Civi")
    assert "body" not in scheduled.reminder
    assert publisher.events[0]["event_type"] == "reminder.scheduled"
    assert publisher.events[0]["producer"] == "notification-service"
    assert publisher.events[0]["to_tail"] == "****2233"


@pytest.mark.asyncio
async def test_process_due_reminders_queues_messages_and_publishes_events() -> None:
    repo = InMemoryNotificationRepository()
    due = repo.schedule_reminder(
        user_key="user-due",
        to="573001112233",
        body="Recordatorio Civi",
        remind_at="2026-07-10T09:00",
    )
    repo.schedule_reminder(
        user_key="user-future",
        to="573001112244",
        body="Recordatorio futuro",
        remind_at="2026-07-11T09:00",
    )
    publisher = InMemoryEventPublisher()

    processed = await process_due_reminders(
        now="2026-07-10T09:30",
        notification_repository=repo,
        event_publisher=publisher,
    )

    assert processed.count == 1
    assert processed.processed[0]["reminder"]["id"] == due.id
    assert processed.processed[0]["reminder"]["status"] == "queued"
    assert processed.processed[0]["message"]["status"] == "queued"
    assert "body" not in processed.processed[0]["reminder"]
    assert "body" not in processed.processed[0]["message"]
    assert [event["event_type"] for event in publisher.events] == ["reminder.due", "notification.queued"]
    assert publisher.events[0]["reminder_id"] == due.id
    assert publisher.events[1]["to_tail"] == "****2233"


@pytest.mark.asyncio
async def test_notification_worker_run_once_processes_due_without_dispatch(monkeypatch: pytest.MonkeyPatch) -> None:
    process_calls: list[dict[str, object]] = []

    async def fake_process_due_reminders(**kwargs: object) -> ProcessDueRemindersResponse:
        process_calls.append(kwargs)
        return ProcessDueRemindersResponse(processed=[{"reminder": {"id": 1}}], count=1)

    async def fake_dispatch_outbox(**kwargs: object) -> None:
        raise AssertionError("dispatch_outbox should not run when disabled")

    monkeypatch.setattr(reminder_worker, "process_due_reminders", fake_process_due_reminders)
    monkeypatch.setattr(reminder_worker, "dispatch_outbox", fake_dispatch_outbox)

    result = await reminder_worker.run_once(
        now="2026-07-10T09:30",
        limit=7,
        dispatch_outbox_enabled=False,
    )

    assert result.due_processed == 1
    assert result.outbox_dispatched == 0
    assert process_calls == [{"now": "2026-07-10T09:30", "limit": 7}]


@pytest.mark.asyncio
async def test_notification_worker_run_once_can_dispatch_outbox(monkeypatch: pytest.MonkeyPatch) -> None:
    async def fake_process_due_reminders(**kwargs: object) -> ProcessDueRemindersResponse:
        return ProcessDueRemindersResponse(processed=[], count=0)

    async def fake_dispatch_outbox(**kwargs: object):
        assert kwargs == {"limit": 3}
        from notification_service.slices.dispatch_outbox.schemas import DispatchOutboxResponse

        return DispatchOutboxResponse(dispatched=[{"id": 1}, {"id": 2}])

    monkeypatch.setattr(reminder_worker, "process_due_reminders", fake_process_due_reminders)
    monkeypatch.setattr(reminder_worker, "dispatch_outbox", fake_dispatch_outbox)

    result = await reminder_worker.run_once(limit=3, dispatch_outbox_enabled=True)

    assert result.due_processed == 0
    assert result.outbox_dispatched == 2
