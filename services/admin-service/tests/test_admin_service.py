import json

import pytest
from fastapi import HTTPException
from fastapi.testclient import TestClient

from admin_service.main import app
from admin_service.adapters.outbound.service_status_client import InternalServiceStatusClient, service_urls_from_env
from admin_service.adapters.outbound.sql_audit_repository import SqlAdminAuditRepository
from admin_service.shared.audit_repository import InMemoryAdminAuditRepository
from admin_service.shared.auth import require_admin_basic
from admin_service.slices.consume_internal_event.schemas import ConsumeInternalEventRequest
from admin_service.slices.consume_internal_event.use_case import consume_internal_event
from admin_service.slices.list_dashboard_citas.use_case import dashboard_summary
from admin_service.workers.event_audit import consume_raw_event


class FakeStatusClient:
    async def fetch_statuses(self) -> list[dict[str, object]]:
        return [
            {"service": "channel-gateway", "status": "ok"},
            {"service": "conversation-service", "status": "ok"},
        ]


@pytest.mark.asyncio
async def test_admin_auth_fail_closed_when_missing_env(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.delenv("ADMIN_USER", raising=False)
    monkeypatch.delenv("ADMIN_PASSWORD", raising=False)

    with pytest.raises(HTTPException) as exc:
        await require_admin_basic(x_admin_user="admin", x_admin_password="admin")

    assert exc.value.status_code == 503


@pytest.mark.asyncio
async def test_admin_auth_accepts_configured_credentials(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("ADMIN_USER", "admin")
    monkeypatch.setenv("ADMIN_PASSWORD", "secret")

    assert await require_admin_basic(x_admin_user="admin", x_admin_password="secret") == "admin"


@pytest.mark.asyncio
async def test_dashboard_summary_uses_service_contract_note() -> None:
    summary = await dashboard_summary(status_client=FakeStatusClient())

    assert summary.success
    assert "bot-orchestrator" in summary.services
    assert summary.service_statuses[0]["service"] == "channel-gateway"
    assert not summary.appointments_visible


@pytest.mark.asyncio
async def test_dashboard_summary_degrades_when_service_token_missing(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.delenv("INTERNAL_SERVICE_TOKEN", raising=False)

    summary = await dashboard_summary()

    assert summary.service_statuses
    assert all(item["status"] == "degraded" for item in summary.service_statuses)


def test_admin_service_urls_from_env(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("VEHICLE_SERVICE_URL", "http://vehicle.internal:8083/")

    assert service_urls_from_env()["vehicle-service"] == "http://vehicle.internal:8083"


def test_admin_status_client_requires_internal_token(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.delenv("INTERNAL_SERVICE_TOKEN", raising=False)

    with pytest.raises(RuntimeError, match="INTERNAL_SERVICE_TOKEN"):
        InternalServiceStatusClient()


def test_admin_internal_dashboard_requires_admin_headers(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("ADMIN_USER", "admin")
    monkeypatch.setenv("ADMIN_PASSWORD", "secret")

    client = TestClient(app)
    unauthorized = client.get("/internal/admin/dashboard/summary")
    assert unauthorized.status_code == 401

    authorized = client.get(
        "/internal/admin/dashboard/summary",
        headers={"X-Admin-User": "admin", "X-Admin-Password": "secret"},
    )
    assert authorized.status_code == 200
    assert authorized.json()["appointments_visible"] is False
    assert authorized.json()["service_statuses"]


def test_admin_audit_endpoint_records_and_lists_actions(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("ADMIN_USER", "audit-admin")
    monkeypatch.setenv("ADMIN_PASSWORD", "secret")
    client = TestClient(app)
    headers = {"X-Admin-User": "audit-admin", "X-Admin-Password": "secret"}

    unauthorized = client.get("/internal/admin/audit")
    assert unauthorized.status_code == 401

    dashboard = client.get("/internal/admin/dashboard/summary", headers=headers)
    assert dashboard.status_code == 200
    audit = client.get("/internal/admin/audit", headers=headers)

    assert audit.status_code == 200
    actions = [event["action"] for event in audit.json()["events"]]
    assert "admin.dashboard.summary" in actions
    assert "admin.audit.list" in actions


@pytest.mark.asyncio
async def test_consume_internal_event_records_sanitized_audit_detail() -> None:
    repo = InMemoryAdminAuditRepository()

    response = await consume_internal_event(
        ConsumeInternalEventRequest(
            event_id="event-1",
            event_type="message.received",
            producer="channel-gateway",
            user_key="573001112233",
            channel="whatsapp",
            text="mi cedula es 123456789",
        ),
        audit_repository=repo,
    )

    events = repo.list_events()
    assert response.audit_event_id == events[0].id
    assert events[0].actor == "channel-gateway"
    assert events[0].action == "event.message.received"
    assert events[0].target == "user_tail:2233"
    assert events[0].outcome == "consumed"
    assert events[0].detail is not None
    assert "573001112233" not in events[0].detail
    assert "123456789" not in events[0].detail
    assert '"user_tail":"2233"' in events[0].detail


def test_admin_internal_event_consumer_requires_service_token(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("INTERNAL_SERVICE_TOKEN", "internal-test-token")
    client = TestClient(app)
    payload = {
        "event_id": "event-http-1",
        "event_type": "conversation.completed",
        "producer": "conversation-service",
        "user_key": "web-user-1234",
        "channel": "web",
        "state_version": 2,
    }

    assert client.post("/internal/admin/events", json=payload).status_code == 401

    response = client.post(
        "/internal/admin/events",
        json=payload,
        headers={"Authorization": "Bearer internal-test-token"},
    )

    assert response.status_code == 200
    assert response.json()["success"] is True
    assert isinstance(response.json()["audit_event_id"], int)


@pytest.mark.asyncio
async def test_event_audit_worker_consumes_raw_event_without_redis() -> None:
    repo = InMemoryAdminAuditRepository()

    audit_event_id = await consume_raw_event(
        json.dumps({
            "event_id": "event-worker-1",
            "event_type": "notification.sent",
            "producer": "notification-service",
            "message_id": 42,
            "channel": "whatsapp",
            "provider": "fake-provider",
            "provider_message_id": "provider-secret-id",
        }),
        audit_repository=repo,
    )

    events = repo.list_events()
    assert audit_event_id == events[0].id
    assert events[0].target == "notification:42"
    assert events[0].detail is not None
    assert "provider-secret-id" not in events[0].detail
    assert '"provider":"fake-provider"' in events[0].detail


def test_sql_admin_audit_repository_persists_events() -> None:
    repo = SqlAdminAuditRepository("sqlite+pysqlite:///:memory:", create_schema=True)

    created = repo.record(
        actor="admin",
        action="admin.dashboard.summary",
        target="admin.dashboard",
    )
    events = repo.list_events()

    assert events[0].id == created.id
    assert events[0].actor == "admin"
    assert events[0].action == "admin.dashboard.summary"


def test_admin_internal_status_requires_service_token(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("INTERNAL_SERVICE_TOKEN", "internal-test-token")
    client = TestClient(app)

    assert client.get("/internal/status").status_code == 401

    response = client.get(
        "/internal/status",
        headers={"Authorization": "Bearer internal-test-token"},
    )
    assert response.status_code == 200
    assert response.json()["service"] == "admin-service"
