from __future__ import annotations

import pytest
from civi_common.events import InMemoryEventPublisher
from fastapi.testclient import TestClient

from conversation_service.adapters.outbound.sql_repository import SqlConversationRepository
from conversation_service.main import app
from conversation_service.shared.repository import InMemoryConversationRepository
from conversation_service.slices.manage_consent.schemas import UpdateConsentRequest
from conversation_service.slices.manage_consent.use_case import get_consent, update_consent
from conversation_service.slices.run_turn.schemas import RunTurnRequest
from conversation_service.slices.run_turn.schemas import RunTurnResponse
from conversation_service.slices.run_turn.use_case import run_turn


class FakeAgentClient:
    def __init__(self) -> None:
        self.calls = 0
        self.payloads: list[RunTurnRequest] = []

    async def run_turn(self, payload: RunTurnRequest) -> dict[str, object]:
        self.calls += 1
        self.payloads.append(payload)
        return {"text": f"respuesta para {payload.text}", "state_version": 3}


class GuardedAgentClient:
    def __init__(self) -> None:
        self.calls = 0

    async def run_turn(self, payload: RunTurnRequest) -> dict[str, object]:
        self.calls += 1
        raise AssertionError("agent must not be called before accepted consent")


class FakeConsentClassifier:
    def __init__(self, classification: str) -> None:
        self.classification = classification
        self.calls = 0
        self.payloads: list[dict[str, str]] = []

    async def classify(self, *, text: str, user_key: str, channel: str) -> str:
        self.calls += 1
        self.payloads.append({"text": text, "user_key": user_key, "channel": channel})
        return self.classification


class FailingConsentClassifier:
    def __init__(self) -> None:
        self.calls = 0

    async def classify(self, *, text: str, user_key: str, channel: str) -> str:
        self.calls += 1
        raise RuntimeError("classifier unavailable")


async def fake_run_turn(payload):
    return RunTurnResponse(user_key=payload.user_key, text="turno procesado", state_version=2)


def test_internal_conversation_turn_requires_token(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("INTERNAL_SERVICE_TOKEN", "internal-test-token")
    monkeypatch.setattr("conversation_service.slices.run_turn.api.run_turn", fake_run_turn)

    client = TestClient(app)
    unauthorized = client.post(
        "/internal/conversations/turns",
        json={"user_key": "web-user", "text": "hola", "channel": "web"},
    )
    assert unauthorized.status_code == 401

    authorized = client.post(
        "/internal/conversations/turns",
        json={"user_key": "web-user", "text": "hola", "channel": "web"},
        headers={"Authorization": "Bearer internal-test-token"},
    )
    assert authorized.status_code == 200
    assert authorized.json() == {"user_key": "web-user", "text": "turno procesado", "state_version": 2}


def test_conversation_internal_status_requires_token(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("INTERNAL_SERVICE_TOKEN", "internal-test-token")
    client = TestClient(app)

    assert client.get("/internal/status").status_code == 401

    response = client.get(
        "/internal/status",
        headers={"Authorization": "Bearer internal-test-token"},
    )
    assert response.status_code == 200
    assert response.json()["service"] == "conversation-service"


def test_conversation_history_requires_token(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("INTERNAL_SERVICE_TOKEN", "internal-test-token")
    client = TestClient(app)

    assert client.get("/internal/conversations/history", params={"user_key": "web-user"}).status_code == 401

    response = client.get(
        "/internal/conversations/history",
        params={"user_key": "web-user"},
        headers={"Authorization": "Bearer internal-test-token"},
    )
    assert response.status_code == 200
    assert "turns" in response.json()


def test_conversation_consent_requires_token(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("INTERNAL_SERVICE_TOKEN", "internal-test-token")
    client = TestClient(app)

    assert client.get("/internal/conversations/consent", params={"user_key": "web-user"}).status_code == 401

    response = client.get(
        "/internal/conversations/consent",
        params={"user_key": "web-user"},
        headers={"Authorization": "Bearer internal-test-token"},
    )
    assert response.status_code == 200
    assert response.json()["status"] == "unknown"


@pytest.mark.asyncio
async def test_run_turn_records_conversation_history() -> None:
    repo = InMemoryConversationRepository()
    publisher = InMemoryEventPublisher()
    agent = FakeAgentClient()
    repo.set_consent(
        user_key="user-history",
        channel="web",
        status="accepted",
        purpose="civi_conversation",
        policy_version="2026-07-07",
    )

    response = await run_turn(
        RunTurnRequest(user_key="user-history", text="hola", channel="web"),
        agent_client=agent,
        conversation_repository=repo,
        event_publisher=publisher,
    )

    assert agent.calls == 1
    assert response.text == "respuesta para hola"
    history = repo.list_for_user(user_key="user-history")
    assert len(history) == 1
    assert history[0].user_text == "hola"
    assert history[0].agent_text == "respuesta para hola"
    assert history[0].state_version == 3
    assert publisher.events[0]["event_type"] == "conversation.completed"
    assert publisher.events[0]["producer"] == "conversation-service"
    assert publisher.events[0]["user_key"] == "user-history"
    assert publisher.events[0]["state_version"] == 3


@pytest.mark.asyncio
async def test_run_turn_forwards_metadata_to_agent() -> None:
    repo = InMemoryConversationRepository()
    publisher = InMemoryEventPublisher()
    agent = FakeAgentClient()
    repo.set_consent(
        user_key="user-location",
        channel="whatsapp",
        status="accepted",
        purpose="civi_conversation",
        policy_version="2026-07-07",
    )

    await run_turn(
        RunTurnRequest(
            user_key="user-location",
            text="pin",
            channel="whatsapp",
            metadata={"location_lat": 4.711, "location_lng": -74.0721},
        ),
        agent_client=agent,
        conversation_repository=repo,
        event_publisher=publisher,
    )

    assert agent.calls == 1
    metadata = agent.payloads[0].metadata
    assert metadata["location_lat"] == 4.711
    assert metadata["location_lng"] == -74.0721
    assert metadata["recent_turns"] == []


@pytest.mark.asyncio
async def test_run_turn_attaches_recent_turns_for_llm_memory() -> None:
    repo = InMemoryConversationRepository()
    publisher = InMemoryEventPublisher()
    agent = FakeAgentClient()
    repo.set_consent(
        user_key="user-memory",
        channel="whatsapp",
        status="accepted",
        purpose="civi_conversation",
        policy_version="2026-07-07",
    )
    for idx in range(5):
        repo.record_turn(
            user_key="user-memory",
            channel="whatsapp",
            user_text=f"msg-{idx}",
            agent_text=f"reply-{idx}",
            state_version=1,
        )

    await run_turn(
        RunTurnRequest(user_key="user-memory", text="y eso cuanto vale?", channel="whatsapp"),
        agent_client=agent,
        conversation_repository=repo,
        event_publisher=publisher,
    )

    recent = agent.payloads[0].metadata["recent_turns"]
    assert len(recent) == 4
    assert recent[0]["user_text"] == "msg-1"
    assert recent[-1]["agent_text"] == "reply-4"


@pytest.mark.asyncio
async def test_run_turn_requests_consent_before_agent_without_storing_raw_text() -> None:
    repo = InMemoryConversationRepository()
    publisher = InMemoryEventPublisher()
    agent = GuardedAgentClient()

    response = await run_turn(
        RunTurnRequest(user_key="user-consent-pending", text="mi cedula es 123456789", channel="web"),
        agent_client=agent,
        conversation_repository=repo,
        event_publisher=publisher,
    )

    assert agent.calls == 0
    assert "autorizacion" in response.text
    history = repo.list_for_user(user_key="user-consent-pending")
    assert len(history) == 1
    assert history[0].user_text == "[consent_pending_message_redacted]"
    assert "123456789" not in history[0].user_text
    assert repo.get_consent(user_key="user-consent-pending", channel="web") is None
    assert [event["event_type"] for event in publisher.events] == ["conversation.completed"]


@pytest.mark.asyncio
async def test_run_turn_accepts_consent_without_calling_agent() -> None:
    repo = InMemoryConversationRepository()
    publisher = InMemoryEventPublisher()
    agent = GuardedAgentClient()
    classifier = FakeConsentClassifier("DECLINE")

    response = await run_turn(
        RunTurnRequest(user_key="user-consent-accepted", text="si acepto", channel="web"),
        agent_client=agent,
        consent_classifier=classifier,
        conversation_repository=repo,
        event_publisher=publisher,
    )

    consent = repo.get_consent(user_key="user-consent-accepted", channel="web")

    assert agent.calls == 0
    assert classifier.calls == 0
    assert "consentimiento" in response.text
    assert "asistente integral de tránsito" in response.text
    assert consent is not None
    assert consent.status == "accepted"
    history = repo.list_for_user(user_key="user-consent-accepted")
    assert history[0].user_text == "[consent_accepted]"
    assert [event["event_type"] for event in publisher.events] == ["consent.updated", "conversation.completed"]
    assert publisher.events[0]["status"] == "accepted"


@pytest.mark.asyncio
async def test_run_turn_declines_consent_without_calling_agent() -> None:
    repo = InMemoryConversationRepository()
    publisher = InMemoryEventPublisher()
    agent = GuardedAgentClient()
    classifier = FakeConsentClassifier("ACCEPT")

    response = await run_turn(
        RunTurnRequest(user_key="user-consent-declined", text="no autorizo", channel="web"),
        agent_client=agent,
        consent_classifier=classifier,
        conversation_repository=repo,
        event_publisher=publisher,
    )

    consent = repo.get_consent(user_key="user-consent-declined", channel="web")

    assert agent.calls == 0
    assert classifier.calls == 0
    assert "Sin consentimiento" in response.text
    assert consent is not None
    assert consent.status == "declined"
    history = repo.list_for_user(user_key="user-consent-declined")
    assert history[0].user_text == "[consent_declined]"
    assert [event["event_type"] for event in publisher.events] == ["consent.updated", "conversation.completed"]
    assert publisher.events[0]["status"] == "declined"


@pytest.mark.asyncio
async def test_run_turn_no_acepto_is_decline_not_accept() -> None:
    repo = InMemoryConversationRepository()
    publisher = InMemoryEventPublisher()
    agent = GuardedAgentClient()
    classifier = FakeConsentClassifier("ACCEPT")

    response = await run_turn(
        RunTurnRequest(user_key="user-no-acepto", text="no acepto", channel="web"),
        agent_client=agent,
        consent_classifier=classifier,
        conversation_repository=repo,
        event_publisher=publisher,
    )

    consent = repo.get_consent(user_key="user-no-acepto", channel="web")

    assert agent.calls == 0
    assert classifier.calls == 0
    assert "Sin consentimiento" in response.text
    assert consent is not None
    assert consent.status == "declined"


@pytest.mark.asyncio
async def test_run_turn_answers_privacy_question_without_agent_or_raw_storage() -> None:
    repo = InMemoryConversationRepository()
    publisher = InMemoryEventPublisher()
    agent = GuardedAgentClient()
    classifier = FakeConsentClassifier("ACCEPT")

    response = await run_turn(
        RunTurnRequest(user_key="user-privacy-question", text="que datos guardas de mi cedula 123456789", channel="web"),
        agent_client=agent,
        consent_classifier=classifier,
        conversation_repository=repo,
        event_publisher=publisher,
    )

    history = repo.list_for_user(user_key="user-privacy-question")

    assert agent.calls == 0
    assert classifier.calls == 0
    assert "Solo guardo" in response.text
    assert repo.get_consent(user_key="user-privacy-question", channel="web") is None
    assert history[0].user_text == "[consent_pending_message_redacted]"
    assert "123456789" not in history[0].agent_text


@pytest.mark.asyncio
async def test_run_turn_uses_consent_classifier_for_ambiguous_acceptance() -> None:
    repo = InMemoryConversationRepository()
    publisher = InMemoryEventPublisher()
    agent = GuardedAgentClient()
    classifier = FakeConsentClassifier("ACCEPT")

    response = await run_turn(
        RunTurnRequest(user_key="user-ambiguous-accept", text="creo que si", channel="web"),
        agent_client=agent,
        consent_classifier=classifier,
        conversation_repository=repo,
        event_publisher=publisher,
    )

    consent = repo.get_consent(user_key="user-ambiguous-accept", channel="web")

    assert agent.calls == 0
    assert classifier.calls == 1
    assert classifier.payloads[0]["text"] == "creo que si"
    assert "consentimiento" in response.text
    assert consent is not None
    assert consent.status == "accepted"
    assert [event["event_type"] for event in publisher.events] == ["consent.updated", "conversation.completed"]


@pytest.mark.asyncio
async def test_run_turn_uses_consent_classifier_for_ambiguous_question() -> None:
    repo = InMemoryConversationRepository()
    publisher = InMemoryEventPublisher()
    agent = GuardedAgentClient()
    classifier = FakeConsentClassifier("QUESTION")

    response = await run_turn(
        RunTurnRequest(user_key="user-ambiguous-question", text="hagamosle pero explicame", channel="web"),
        agent_client=agent,
        consent_classifier=classifier,
        conversation_repository=repo,
        event_publisher=publisher,
    )

    history = repo.list_for_user(user_key="user-ambiguous-question")

    assert agent.calls == 0
    assert classifier.calls == 1
    assert "Solo guardo" in response.text
    assert repo.get_consent(user_key="user-ambiguous-question", channel="web") is None
    assert history[0].user_text == "[consent_pending_message_redacted]"
    assert [event["event_type"] for event in publisher.events] == ["conversation.completed"]


@pytest.mark.asyncio
async def test_run_turn_failing_consent_classifier_reasks_without_accepting() -> None:
    repo = InMemoryConversationRepository()
    publisher = InMemoryEventPublisher()
    agent = GuardedAgentClient()
    classifier = FailingConsentClassifier()

    response = await run_turn(
        RunTurnRequest(user_key="user-classifier-failure", text="pues bueno", channel="web"),
        agent_client=agent,
        consent_classifier=classifier,
        conversation_repository=repo,
        event_publisher=publisher,
    )

    assert agent.calls == 0
    assert classifier.calls == 1
    assert "Responde *si* o *no*" in response.text
    assert repo.get_consent(user_key="user-classifier-failure", channel="web") is None
    assert [event["event_type"] for event in publisher.events] == ["conversation.completed"]


@pytest.mark.asyncio
async def test_run_turn_hard_reset_clears_channel_history_and_consent_before_agent() -> None:
    repo = InMemoryConversationRepository()
    publisher = InMemoryEventPublisher()
    agent = GuardedAgentClient()
    classifier = FakeConsentClassifier("ACCEPT")
    repo.set_consent(
        user_key="user-reset",
        channel="whatsapp",
        status="accepted",
        purpose="civi_conversation",
        policy_version="2026-07-07",
    )
    repo.set_consent(
        user_key="user-reset",
        channel="web",
        status="accepted",
        purpose="civi_conversation",
        policy_version="2026-07-07",
    )
    repo.record_turn(
        user_key="user-reset",
        channel="whatsapp",
        user_text="hola",
        agent_text="respuesta",
        state_version=2,
    )
    repo.record_turn(
        user_key="user-reset",
        channel="web",
        user_text="hola web",
        agent_text="respuesta web",
        state_version=2,
    )

    response = await run_turn(
        RunTurnRequest(user_key="user-reset", text="/reset", channel="whatsapp"),
        agent_client=agent,
        consent_classifier=classifier,
        conversation_repository=repo,
        event_publisher=publisher,
    )

    web_consent = repo.get_consent(user_key="user-reset", channel="web")

    assert agent.calls == 0
    assert classifier.calls == 0
    assert "historial y el consentimiento" in response.text
    assert "Habeas Data" in response.text
    assert response.state_version == 0
    assert repo.get_consent(user_key="user-reset", channel="whatsapp") is None
    assert web_consent is not None
    assert web_consent.status == "accepted"
    assert repo.count_for_user(user_key="user-reset", channel="whatsapp") == 0
    assert repo.count_for_user(user_key="user-reset", channel="web") == 1
    assert [event["event_type"] for event in publisher.events] == ["conversation.completed"]
    assert publisher.events[0]["state_version"] == 0

    next_response = await run_turn(
        RunTurnRequest(user_key="user-reset", text="hola", channel="whatsapp"),
        agent_client=agent,
        conversation_repository=repo,
        event_publisher=publisher,
    )

    assert agent.calls == 0
    assert "autorizacion" in next_response.text


@pytest.mark.asyncio
async def test_run_turn_soft_reset_keeps_consent_before_agent() -> None:
    repo = InMemoryConversationRepository()
    publisher = InMemoryEventPublisher()
    guarded_agent = GuardedAgentClient()
    repo.set_consent(
        user_key="user-soft-reset",
        channel="whatsapp",
        status="accepted",
        purpose="civi_conversation",
        policy_version="2026-07-07",
    )
    repo.record_turn(
        user_key="user-soft-reset",
        channel="whatsapp",
        user_text="hola",
        agent_text="respuesta",
        state_version=2,
    )

    response = await run_turn(
        RunTurnRequest(user_key="user-soft-reset", text="/reset-soft", channel="whatsapp"),
        agent_client=guarded_agent,
        conversation_repository=repo,
        event_publisher=publisher,
    )

    consent = repo.get_consent(user_key="user-soft-reset", channel="whatsapp")

    assert guarded_agent.calls == 0
    assert "conserve el consentimiento" in response.text
    assert consent is not None
    assert consent.status == "accepted"
    assert repo.count_for_user(user_key="user-soft-reset", channel="whatsapp") == 0

    normal_agent = FakeAgentClient()
    normal_response = await run_turn(
        RunTurnRequest(user_key="user-soft-reset", text="hola", channel="whatsapp"),
        agent_client=normal_agent,
        conversation_repository=repo,
        event_publisher=publisher,
    )

    assert normal_agent.calls == 1
    assert normal_response.text == "respuesta para hola"


@pytest.mark.asyncio
async def test_run_turn_status_command_reports_current_channel_without_agent() -> None:
    repo = InMemoryConversationRepository()
    publisher = InMemoryEventPublisher()
    agent = GuardedAgentClient()
    repo.set_consent(
        user_key="user-status",
        channel="whatsapp",
        status="accepted",
        purpose="civi_conversation",
        policy_version="2026-07-07",
    )
    repo.record_turn(
        user_key="user-status",
        channel="whatsapp",
        user_text="hola",
        agent_text="respuesta",
        state_version=2,
    )

    response = await run_turn(
        RunTurnRequest(user_key="user-status", text="/estado", channel="whatsapp"),
        agent_client=agent,
        conversation_repository=repo,
        event_publisher=publisher,
    )

    assert agent.calls == 0
    assert "consentimiento *aceptado*" in response.text
    assert "turnos guardados: *1*" in response.text
    assert response.state_version == 0


def test_sql_conversation_repository_persists_history() -> None:
    repo = SqlConversationRepository("sqlite+pysqlite:///:memory:", create_schema=True)

    record = repo.record_turn(
        user_key="user-sql",
        channel="web",
        user_text="hola",
        agent_text="respuesta",
        state_version=2,
    )

    history = repo.list_for_user(user_key="user-sql")
    assert history[0].id == record.id
    assert history[0].agent_text == "respuesta"


def test_sql_conversation_repository_clears_history_and_consent_by_channel() -> None:
    repo = SqlConversationRepository("sqlite+pysqlite:///:memory:", create_schema=True)
    repo.set_consent(
        user_key="user-sql-reset",
        channel="whatsapp",
        status="accepted",
        purpose="civi_conversation",
        policy_version="2026-07-07",
    )
    repo.set_consent(
        user_key="user-sql-reset",
        channel="web",
        status="accepted",
        purpose="civi_conversation",
        policy_version="2026-07-07",
    )
    repo.record_turn(
        user_key="user-sql-reset",
        channel="whatsapp",
        user_text="hola",
        agent_text="respuesta",
        state_version=2,
    )
    repo.record_turn(
        user_key="user-sql-reset",
        channel="web",
        user_text="hola web",
        agent_text="respuesta web",
        state_version=2,
    )

    assert repo.count_for_user(user_key="user-sql-reset", channel="whatsapp") == 1
    assert repo.clear_history(user_key="user-sql-reset", channel="whatsapp") == 1
    assert repo.clear_consent(user_key="user-sql-reset", channel="whatsapp") is True

    web_consent = repo.get_consent(user_key="user-sql-reset", channel="web")

    assert repo.count_for_user(user_key="user-sql-reset", channel="whatsapp") == 0
    assert repo.count_for_user(user_key="user-sql-reset", channel="web") == 1
    assert repo.get_consent(user_key="user-sql-reset", channel="whatsapp") is None
    assert web_consent is not None
    assert web_consent.status == "accepted"


@pytest.mark.asyncio
async def test_update_consent_persists_and_publishes_event() -> None:
    repo = InMemoryConversationRepository()
    publisher = InMemoryEventPublisher()

    response = await update_consent(
        UpdateConsentRequest(
            user_key="user-consent",
            channel="whatsapp",
            status="accepted",
            purpose="civi_conversation",
            policy_version="2026-07-07",
        ),
        conversation_repository=repo,
        event_publisher=publisher,
    )
    loaded = await get_consent(user_key="user-consent", channel="whatsapp", conversation_repository=repo)

    assert response.status == "accepted"
    assert loaded.status == "accepted"
    assert publisher.events[0]["event_type"] == "consent.updated"
    assert publisher.events[0]["producer"] == "conversation-service"
    assert publisher.events[0]["status"] == "accepted"


def test_sql_conversation_repository_persists_consent() -> None:
    repo = SqlConversationRepository("sqlite+pysqlite:///:memory:", create_schema=True)

    record = repo.set_consent(
        user_key="user-sql-consent",
        channel="web",
        status="declined",
        purpose="civi_conversation",
        policy_version="2026-07-07",
    )
    loaded = repo.get_consent(user_key="user-sql-consent", channel="web")

    assert loaded is not None
    assert loaded.status == "declined"
    assert loaded.updated_at == record.updated_at
