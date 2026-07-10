from __future__ import annotations

import os
from datetime import datetime, timedelta
from zoneinfo import ZoneInfo

BOGOTA = ZoneInfo("America/Bogota")


def compute_remind_at(starts_at: str, *, lead_minutes: int | None = None) -> str:
    if lead_minutes is None:
        lead_minutes = _lead_minutes_from_env()

    dt = datetime.fromisoformat(starts_at)
    if dt.tzinfo is None:
        dt = dt.replace(tzinfo=BOGOTA)

    remind = dt - timedelta(minutes=lead_minutes)
    return remind.astimezone(ZoneInfo("UTC")).isoformat(timespec="seconds")


def client_lead_minutes() -> int:
    return _lead_minutes_from_env("APPOINTMENT_REMINDER_LEAD_MINUTES", default=30)


def partner_lead_minutes() -> int:
    return _lead_minutes_from_env("APPOINTMENT_PARTNER_REMINDER_LEAD_MINUTES", default=60)


def _lead_minutes_from_env(name: str = "APPOINTMENT_REMINDER_LEAD_MINUTES", *, default: int = 30) -> int:
    raw = os.getenv(name, str(default)).strip()
    try:
        value = int(raw)
    except ValueError:
        return default
    return value if value >= 0 else default
