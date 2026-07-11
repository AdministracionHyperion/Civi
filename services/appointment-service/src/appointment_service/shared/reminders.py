from __future__ import annotations

import os
from datetime import datetime, timedelta
from zoneinfo import ZoneInfo

BOGOTA = ZoneInfo("America/Bogota")


def format_starts_at_human(starts_at: str) -> str:
    """Render ISO-like starts_at as a short Spanish datetime for WhatsApp."""
    raw = (starts_at or "").strip()
    if not raw:
        return starts_at
    try:
        dt = datetime.fromisoformat(raw.replace("Z", "+00:00"))
    except ValueError:
        return starts_at
    if dt.tzinfo is None:
        dt = dt.replace(tzinfo=BOGOTA)
    else:
        dt = dt.astimezone(BOGOTA)

    hour24 = dt.hour
    minute = dt.minute
    suffix = "a. m." if hour24 < 12 else "p. m."
    hour12 = hour24 % 12 or 12
    time_part = f"{hour12}:{minute:02d} {suffix}"
    return f"{dt.day:02d}/{dt.month:02d}/{dt.year} a las {time_part}"


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
