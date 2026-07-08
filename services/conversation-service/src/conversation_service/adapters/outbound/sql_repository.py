from __future__ import annotations

from datetime import UTC, datetime

from sqlalchemy import Column, Integer, MetaData, String, Table, create_engine, func, select, update
from sqlalchemy.engine import Engine

from conversation_service.shared.repository import ConversationConsentRecord, ConversationTurnRecord

metadata = MetaData()

conversation_turns = Table(
    "conversation_turns",
    metadata,
    Column("id", Integer, primary_key=True, autoincrement=True),
    Column("user_key", String(128), nullable=False, index=True),
    Column("channel", String(32), nullable=False),
    Column("user_text", String(4096), nullable=False),
    Column("agent_text", String(4096), nullable=False),
    Column("state_version", Integer, nullable=False),
    Column("created_at", String(64), nullable=False),
)

conversation_consents = Table(
    "conversation_consents",
    metadata,
    Column("user_key", String(128), primary_key=True),
    Column("channel", String(32), primary_key=True),
    Column("status", String(32), nullable=False),
    Column("purpose", String(128), nullable=False),
    Column("policy_version", String(64), nullable=False),
    Column("updated_at", String(64), nullable=False),
)


class SqlConversationRepository:
    def __init__(self, database_url: str, *, create_schema: bool = False) -> None:
        self.engine: Engine = create_engine(database_url, future=True)
        if create_schema:
            metadata.create_all(self.engine)

    def record_turn(
        self,
        *,
        user_key: str,
        channel: str,
        user_text: str,
        agent_text: str,
        state_version: int,
    ) -> ConversationTurnRecord:
        created_at = datetime.now(UTC).isoformat(timespec="seconds")
        with self.engine.begin() as conn:
            result = conn.execute(
                conversation_turns.insert().values(
                    user_key=user_key,
                    channel=channel,
                    user_text=user_text,
                    agent_text=agent_text,
                    state_version=state_version,
                    created_at=created_at,
                )
            )
            record_id = int(result.inserted_primary_key[0])
        return ConversationTurnRecord(
            id=record_id,
            user_key=user_key,
            channel=channel,
            user_text=user_text,
            agent_text=agent_text,
            state_version=state_version,
            created_at=created_at,
        )

    def list_for_user(self, *, user_key: str, limit: int = 20) -> list[ConversationTurnRecord]:
        stmt = (
            select(conversation_turns)
            .where(conversation_turns.c.user_key == user_key)
            .order_by(conversation_turns.c.id.desc())
            .limit(limit)
        )
        with self.engine.begin() as conn:
            rows = conn.execute(stmt).mappings().all()
        return [_record_from_row(row) for row in rows]

    def clear_history(self, *, user_key: str, channel: str) -> int:
        stmt = (
            conversation_turns.delete()
            .where(conversation_turns.c.user_key == user_key)
            .where(conversation_turns.c.channel == channel)
        )
        with self.engine.begin() as conn:
            result = conn.execute(stmt)
        return int(result.rowcount or 0)

    def count_for_user(self, *, user_key: str, channel: str) -> int:
        stmt = (
            select(func.count())
            .select_from(conversation_turns)
            .where(conversation_turns.c.user_key == user_key)
            .where(conversation_turns.c.channel == channel)
        )
        with self.engine.begin() as conn:
            count = conn.execute(stmt).scalar_one()
        return int(count)

    def set_consent(
        self,
        *,
        user_key: str,
        channel: str,
        status: str,
        purpose: str,
        policy_version: str,
    ) -> ConversationConsentRecord:
        updated_at = datetime.now(UTC).isoformat(timespec="seconds")
        values = {
            "user_key": user_key,
            "channel": channel,
            "status": status,
            "purpose": purpose,
            "policy_version": policy_version,
            "updated_at": updated_at,
        }
        with self.engine.begin() as conn:
            existing = conn.execute(
                select(conversation_consents.c.user_key)
                .where(conversation_consents.c.user_key == user_key)
                .where(conversation_consents.c.channel == channel)
            ).first()
            if existing is None:
                conn.execute(conversation_consents.insert().values(**values))
            else:
                conn.execute(
                    update(conversation_consents)
                    .where(conversation_consents.c.user_key == user_key)
                    .where(conversation_consents.c.channel == channel)
                    .values(**values)
                )
        return ConversationConsentRecord(**values)

    def get_consent(self, *, user_key: str, channel: str) -> ConversationConsentRecord | None:
        stmt = (
            select(conversation_consents)
            .where(conversation_consents.c.user_key == user_key)
            .where(conversation_consents.c.channel == channel)
        )
        with self.engine.begin() as conn:
            row = conn.execute(stmt).mappings().first()
        return _consent_from_row(row) if row else None

    def clear_consent(self, *, user_key: str, channel: str) -> bool:
        stmt = (
            conversation_consents.delete()
            .where(conversation_consents.c.user_key == user_key)
            .where(conversation_consents.c.channel == channel)
        )
        with self.engine.begin() as conn:
            result = conn.execute(stmt)
        return bool(result.rowcount)


def _record_from_row(row) -> ConversationTurnRecord:
    return ConversationTurnRecord(
        id=int(row["id"]),
        user_key=str(row["user_key"]),
        channel=str(row["channel"]),
        user_text=str(row["user_text"]),
        agent_text=str(row["agent_text"]),
        state_version=int(row["state_version"]),
        created_at=str(row["created_at"]),
    )


def _consent_from_row(row) -> ConversationConsentRecord:
    return ConversationConsentRecord(
        user_key=str(row["user_key"]),
        channel=str(row["channel"]),
        status=str(row["status"]),
        purpose=str(row["purpose"]),
        policy_version=str(row["policy_version"]),
        updated_at=str(row["updated_at"]),
    )
