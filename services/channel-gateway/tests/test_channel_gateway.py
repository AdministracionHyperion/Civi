from __future__ import annotations

import hashlib
import hmac
import json
import pytest
from civi_common.events import InMemoryEventPublisher
from fastapi.testclient import TestClient

from channel_gateway.main import app
from channel_gateway.shared.rate_limit import rate_limiter
from channel_gateway.slices.receive_message.schemas import ReceiveMessageRequest
from channel_gateway.slices.receive_message.schemas import ReceiveMessageResponse
from channel_gateway.slices.receive_message.use_case import receive_message


class FakeConversationClient:
    async def run_turn(self, payload: ReceiveMessageRequest) -> dict[str, object]:
        return {"user_key": payload.user_key, "text": f"respuesta a {payload.text}", "state_version": 1}


async def fake_receive_message(payload):
    return ReceiveMessageResponse(user_key=payload.user_key, text="respuesta civi", source="test")


def test_public_chat_message_calls_gateway_slice(monkeypatch) -> None:
    rate_limiter.clear()
    monkeypatch.setenv("CHANNEL_PUBLIC_RATE_LIMIT_ENABLED", "false")
    monkeypatch.setattr(
        "channel_gateway.slices.receive_message.api.receive_message",
        fake_receive_message,
    )

    client = TestClient(app)
    response = client.post(
        "/chat/messages",
        json={"user_key": "web-user", "text": "hola", "channel": "web"},
    )

    assert response.status_code == 200
    assert response.json() == {"user_key": "web-user", "text": "respuesta civi", "source": "test"}


def test_public_chat_message_rate_limit(monkeypatch: pytest.MonkeyPatch) -> None:
    rate_limiter.clear()
    monkeypatch.setenv("CHANNEL_PUBLIC_RATE_LIMIT_ENABLED", "true")
    monkeypatch.setenv("CHANNEL_PUBLIC_RATE_LIMIT_MAX", "1")
    monkeypatch.setenv("CHANNEL_PUBLIC_RATE_LIMIT_WINDOW_SECONDS", "60")
    monkeypatch.setattr(
        "channel_gateway.slices.receive_message.api.receive_message",
        fake_receive_message,
    )
    client = TestClient(app)

    first = client.post(
        "/chat/messages",
        json={"user_key": "web-user", "text": "hola", "channel": "web"},
    )
    second = client.post(
        "/chat/messages",
        json={"user_key": "web-user", "text": "otra vez", "channel": "web"},
    )

    assert first.status_code == 200
    assert second.status_code == 429
    assert second.headers["Retry-After"]


@pytest.mark.asyncio
async def test_receive_message_publishes_message_received_event() -> None:
    publisher = InMemoryEventPublisher()

    response = await receive_message(
        ReceiveMessageRequest(user_key="web-user", text="hola", channel="web"),
        conversation_client=FakeConversationClient(),
        event_publisher=publisher,
    )

    assert response.text == "respuesta a hola"
    assert publisher.events[0]["event_type"] == "message.received"
    assert publisher.events[0]["producer"] == "channel-gateway"
    assert publisher.events[0]["user_key"] == "web-user"
    assert publisher.events[0]["text"] == "hola"


def test_gateway_internal_status_requires_token(monkeypatch: pytest.MonkeyPatch) -> None:
    rate_limiter.clear()
    monkeypatch.setenv("CHANNEL_PUBLIC_RATE_LIMIT_ENABLED", "true")
    monkeypatch.setenv("CHANNEL_PUBLIC_RATE_LIMIT_MAX", "1")
    monkeypatch.setenv("INTERNAL_SERVICE_TOKEN", "internal-test-token")
    client = TestClient(app)

    assert client.get("/internal/status").status_code == 401

    response = client.get(
        "/internal/status",
        headers={"Authorization": "Bearer internal-test-token"},
    )
    assert response.status_code == 200
    assert response.json()["service"] == "channel-gateway"


def test_whatsapp_webhook_verification_requires_configured_token(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("WHATSAPP_VERIFY_TOKEN", "verify-local")
    client = TestClient(app)

    response = client.get(
        "/webhook/whatsapp",
        params={
            "hub.mode": "subscribe",
            "hub.verify_token": "verify-local",
            "hub.challenge": "challenge-123",
        },
    )

    assert response.status_code == 200
    assert response.text == "challenge-123"


def test_legacy_whatsapp_webhook_verification_path(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("WHATSAPP_VERIFY_TOKEN", "verify-local")
    client = TestClient(app)

    response = client.get(
        "/webhook",
        params={
            "hub.mode": "subscribe",
            "hub.verify_token": "verify-local",
            "hub.challenge": "challenge-legacy",
        },
    )

    assert response.status_code == 200
    assert response.text == "challenge-legacy"


def test_whatsapp_webhook_requires_signature_outside_development(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("APP_ENV", "production")
    monkeypatch.delenv("WHATSAPP_SIGNATURE_REQUIRED", raising=False)
    monkeypatch.setenv("WHATSAPP_APP_SECRET", "app-secret")
    client = TestClient(app)

    response = client.post("/webhook/whatsapp", content=b"{}")

    assert response.status_code == 401


def test_whatsapp_webhook_can_disable_signature_for_legacy_vps(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("APP_ENV", "production")
    monkeypatch.setenv("WHATSAPP_SIGNATURE_REQUIRED", "false")
    monkeypatch.delenv("WHATSAPP_APP_SECRET", raising=False)
    client = TestClient(app)

    response = client.post("/webhook/whatsapp", content=b"{}")

    assert response.status_code == 202
    assert response.json() == {"success": True, "handled": False}


def test_legacy_whatsapp_webhook_post_path(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("APP_ENV", "production")
    monkeypatch.setenv("WHATSAPP_SIGNATURE_REQUIRED", "false")
    client = TestClient(app)

    response = client.post("/webhook", content=b"{}")

    assert response.status_code == 202
    assert response.json() == {"success": True, "handled": False}


def test_whatsapp_webhook_accepts_valid_signature(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("APP_ENV", "production")
    monkeypatch.delenv("WHATSAPP_SIGNATURE_REQUIRED", raising=False)
    monkeypatch.setenv("WHATSAPP_APP_SECRET", "app-secret")
    monkeypatch.setattr(
        "channel_gateway.slices.receive_whatsapp_webhook.api.receive_message",
        fake_receive_message,
    )
    sent_replies: list[tuple[str, str]] = []

    async def fake_send_reply(*, to: str, body: str) -> None:
        sent_replies.append((to, body))

    monkeypatch.setattr(
        "channel_gateway.slices.receive_whatsapp_webhook.api._send_whatsapp_reply",
        fake_send_reply,
    )
    body = json.dumps(
        {
            "entry": [
                {
                    "changes": [
                        {
                            "value": {
                                "messages": [
                                    {
                                        "from": "573001112233",
                                        "text": {"body": "hola"},
                                    }
                                ]
                            }
                        }
                    ]
                }
            ]
        },
        separators=(",", ":"),
    ).encode("utf-8")
    signature = "sha256=" + hmac.new(b"app-secret", body, hashlib.sha256).hexdigest()
    client = TestClient(app)

    response = client.post(
        "/webhook/whatsapp",
        content=body,
        headers={"X-Hub-Signature-256": signature, "Content-Type": "application/json"},
    )

    assert response.status_code == 202
    assert response.json()["handled"] is True
    assert response.json()["user_key"] == "573001112233"
    assert response.json()["reply_scheduled"] is True
    assert sent_replies == [("573001112233", "respuesta civi")]


def test_whatsapp_webhook_forwards_location_metadata(monkeypatch: pytest.MonkeyPatch) -> None:
    rate_limiter.clear()
    monkeypatch.setenv("APP_ENV", "development")
    monkeypatch.setenv("CHANNEL_PUBLIC_RATE_LIMIT_ENABLED", "false")
    captured: list[ReceiveMessageRequest] = []

    async def fake_receive_location(payload: ReceiveMessageRequest) -> ReceiveMessageResponse:
        captured.append(payload)
        return ReceiveMessageResponse(user_key=payload.user_key, text="respuesta civi", source="test")

    monkeypatch.setattr(
        "channel_gateway.slices.receive_whatsapp_webhook.api.receive_message",
        fake_receive_location,
    )
    sent_replies: list[tuple[str, str]] = []

    async def fake_send_reply(*, to: str, body: str) -> None:
        sent_replies.append((to, body))

    monkeypatch.setattr(
        "channel_gateway.slices.receive_whatsapp_webhook.api._send_whatsapp_reply",
        fake_send_reply,
    )
    body = {
        "entry": [
            {
                "changes": [
                    {
                        "value": {
                            "contacts": [{"profile": {"name": "Usuario Demo"}}],
                            "messages": [
                                {
                                    "from": "573001112233",
                                    "type": "location",
                                    "location": {
                                        "latitude": 4.711,
                                        "longitude": -74.0721,
                                        "name": "Centro",
                                        "address": "Bogota",
                                    },
                                }
                            ],
                        }
                    }
                ]
            }
        ]
    }
    client = TestClient(app)

    response = client.post("/webhook/whatsapp", json=body)

    assert response.status_code == 202
    assert response.json()["handled"] is True
    assert captured[0].user_key == "573001112233"
    assert captured[0].channel == "whatsapp"
    assert "ubicacion actual" in captured[0].text
    assert captured[0].metadata["location_lat"] == 4.711
    assert captured[0].metadata["location_lng"] == -74.0721
    assert captured[0].metadata["location_source"] == "whatsapp_location"
    assert sent_replies == [("573001112233", "respuesta civi")]
