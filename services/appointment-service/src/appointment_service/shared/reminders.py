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


def _lead_minutes_from_env() -> int:
    raw = os.getenv("APPOINTMENT_REMINDER_LEAD_MINUTES", "30").strip()
    try:
        value = int(raw)
    except ValueError:
        return 30
    return value if value >= 0 else 30
