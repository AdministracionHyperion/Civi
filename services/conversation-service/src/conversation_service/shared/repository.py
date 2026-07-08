from __future__ import annotations

from dataclasses import dataclass, field
from datetime import UTC, datetime
from itertools import count
import os
from threading import Lock
from typing import Protocol


@dataclass
class ConversationTurnRecord:
    id: int
    user_key: str
    channel: str
    user_text: str
    agent_text: str
    state_version: int = 1
    created_at: str = field(default_factory=lambda: datetime.now(UTC).isoformat(timespec="seconds"))


@dataclass
class ConversationConsentRecord:
    user_key: str
    channel: str
    status: str
    purpose: str
    policy_version: str
    updated_at: str = field(default_factory=lambda: datetime.now(UTC).isoformat(timespec="seconds"))


class ConversationRepository(Protocol):
    def record_turn(
        self,
        *,
        user_key: str,
        channel: str,
        user_text: str,
        agent_text: str,
        state_version: int,
    ) -> ConversationTurnRecord:
        ...

    def list_for_user(self, *, user_key: str, limit: int = 20) -> list[ConversationTurnRecord]:
        ...

    def clear_history(self, *, user_key: str, channel: str) -> int:
        ...

    def count_for_user(self, *, user_key: str, channel: str) -> int:
        ...

    def set_consent(
        self,
        *,
        user_key: str,
        channel: str,
        status: str,
        purpose: str,
        policy_version: str,
    ) -> ConversationConsentRecord:
        ...

    def get_consent(self, *, user_key: str, channel: str) -> ConversationConsentRecord | None:
        ...

    def clear_consent(self, *, user_key: str, channel: str) -> bool:
        ...


class InMemoryConversationRepository:
    def __init__(self) -> None:
        self._records: dict[int, ConversationTurnRecord] = {}
        self._consents: dict[tuple[str, str], ConversationConsentRecord] = {}
        self._ids = count(1)
        self._lock = Lock()

    def record_turn(
        self,
        *,
        user_key: str,
        channel: str,
        user_text: str,
        agent_text: str,
        state_version: int,
    ) -> ConversationTurnRecord:
        with self._lock:
            record = ConversationTurnRecord(
                id=next(self._ids),
                user_key=user_key,
                channel=channel,
                user_text=user_text,
                agent_text=agent_text,
                state_version=state_version,
            )
            self._records[record.id] = record
            return record

    def list_for_user(self, *, user_key: str, limit: int = 20) -> list[ConversationTurnRecord]:
        records = [
            record
            for record in sorted(self._records.values(), key=lambda item: item.id, reverse=True)
            if record.user_key == user_key
        ]
        return records[:limit]

    def clear_history(self, *, user_key: str, channel: str) -> int:
        with self._lock:
            matching_ids = [
                record_id
                for record_id, record in self._records.items()
                if record.user_key == user_key and record.channel == channel
            ]
            for record_id in matching_ids:
                del self._records[record_id]
            return len(matching_ids)

    def count_for_user(self, *, user_key: str, channel: str) -> int:
        return sum(1 for record in self._records.values() if record.user_key == user_key and record.channel == channel)

    def set_consent(
        self,
        *,
        user_key: str,
        channel: str,
        status: str,
        purpose: str,
        policy_version: str,
    ) -> ConversationConsentRecord:
        with self._lock:
            record = ConversationConsentRecord(
                user_key=user_key,
                channel=channel,
                status=status,
                purpose=purpose,
                policy_version=policy_version,
            )
            self._consents[(user_key, channel)] = record
            return record

    def get_consent(self, *, user_key: str, channel: str) -> ConversationConsentRecord | None:
        return self._consents.get((user_key, channel))

    def clear_consent(self, *, user_key: str, channel: str) -> bool:
        with self._lock:
            return self._consents.pop((user_key, channel), None) is not None


def repository_from_env() -> ConversationRepository:
    mode = os.getenv("CONVERSATION_REPOSITORY_MODE", "memory").strip().lower()
    if mode in {"", "memory"}:
        return InMemoryConversationRepository()
    if mode == "sql":
        database_url = os.getenv("CONVERSATION_DATABASE_URL", "").strip()
        if not database_url:
            raise RuntimeError("CONVERSATION_DATABASE_URL is required when CONVERSATION_REPOSITORY_MODE=sql")
        from conversation_service.adapters.outbound.sql_repository import SqlConversationRepository

        auto_create = os.getenv("CONVERSATION_AUTO_CREATE_SCHEMA", "").strip().lower() in {"1", "true", "yes"}
        return SqlConversationRepository(database_url, create_schema=auto_create)
    raise RuntimeError(f"unsupported conversation repository mode: {mode}")


repository = repository_from_env()
