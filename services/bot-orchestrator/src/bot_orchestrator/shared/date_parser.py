from __future__ import annotations

import re
import unicodedata
from datetime import datetime, timedelta
from zoneinfo import ZoneInfo


BOGOTA_TZ = ZoneInfo("America/Bogota")

ISO_DATE_RE = re.compile(r"\b(20\d{2})-(\d{2})-(\d{2})(?:[ T](\d{1,2})(?::(\d{2}))?)?\b")
SLASH_DATE_RE = re.compile(r"\b(\d{1,2})/(\d{1,2})/(20\d{2})(?:[ T](\d{1,2})(?::(\d{2}))?)?\b")
RELATIVE_DAYS_RE = re.compile(r"\ben\s+(\d{1,2})\s+dias?\b")
TIME_COLON_RE = re.compile(r"\b(\d{1,2}):(\d{2})\s*(am|pm)?\b")
TIME_COMPACT_RE = re.compile(r"\b(?:a\s+las?|sobre\s+las?)?\s*(\d{1,2})\s*(am|pm)\b")
TIME_HOUR_RE = re.compile(r"\b(?:a\s+las?|sobre\s+las?)\s*(\d{1,2})(?:\s*(?:de\s+la\s+)?(manana|tarde|noche))?\b")
DAY_MONTH_RE = re.compile(
    r"\b(\d{1,2})\s+de\s+"
    r"(enero|febrero|marzo|abril|mayo|junio|julio|agosto|septiembre|setiembre|octubre|noviembre|diciembre)"
    r"(?:\s+de\s+(20\d{2}))?\b"
)

WEEKDAYS = {
    "lunes": 0,
    "martes": 1,
    "miercoles": 2,
    "jueves": 3,
    "viernes": 4,
    "sabado": 5,
    "domingo": 6,
}

MONTHS = {
    "enero": 1,
    "febrero": 2,
    "marzo": 3,
    "abril": 4,
    "mayo": 5,
    "junio": 6,
    "julio": 7,
    "agosto": 8,
    "septiembre": 9,
    "setiembre": 9,
    "octubre": 10,
    "noviembre": 11,
    "diciembre": 12,
}


def parse_natural_datetime(text: str, *, now: datetime | None = None) -> str | None:
    """Parse common Spanish appointment dates into ``YYYY-MM-DDTHH:MM``.

    This parser is deliberately deterministic and dependency-free. It covers the
    WhatsApp phrases Civi asks users to send: ISO dates, slash dates, relative
    days, weekdays, day/month names, and simple Colombian time expressions.
    """

    raw = text or ""
    normalized = _normalize(raw)
    if not normalized:
        return None

    reference = _reference(now)
    explicit_time = _extract_time(normalized)
    daypart_time = _daypart_time(normalized)
    hour, minute = explicit_time or daypart_time or (9, 0)

    explicit_date = _parse_explicit_date(normalized, reference)
    if explicit_date is not None:
        return _format_if_valid(explicit_date.replace(hour=hour, minute=minute), reference)

    relative_date = _parse_relative_date(normalized, reference)
    if relative_date is not None:
        return _format_if_valid(relative_date.replace(hour=hour, minute=minute), reference)

    weekday_date = _parse_weekday(normalized, reference)
    if weekday_date is not None:
        return _format_if_valid(weekday_date.replace(hour=hour, minute=minute), reference)

    return None


def _reference(now: datetime | None) -> datetime:
    if now is None:
        return datetime.now(BOGOTA_TZ).replace(second=0, microsecond=0)
    if now.tzinfo is None:
        return now.replace(tzinfo=BOGOTA_TZ, second=0, microsecond=0)
    return now.astimezone(BOGOTA_TZ).replace(second=0, microsecond=0)


def _parse_explicit_date(text: str, reference: datetime) -> datetime | None:
    match = ISO_DATE_RE.search(text)
    if match:
        year, month, day, hour, minute = match.groups()
        return _safe_datetime(
            int(year),
            int(month),
            int(day),
            int(hour) if hour else 9,
            int(minute) if minute else 0,
        )

    match = SLASH_DATE_RE.search(text)
    if match:
        day, month, year, hour, minute = match.groups()
        return _safe_datetime(
            int(year),
            int(month),
            int(day),
            int(hour) if hour else 9,
            int(minute) if minute else 0,
        )

    match = DAY_MONTH_RE.search(text)
    if match:
        day, month_name, year = match.groups()
        year_value = int(year) if year else reference.year
        candidate = _safe_datetime(year_value, MONTHS[month_name], int(day), 9, 0)
        if candidate is not None and candidate < reference - timedelta(hours=1) and year is None:
            candidate = _safe_datetime(year_value + 1, MONTHS[month_name], int(day), 9, 0)
        return candidate

    return None


def _parse_relative_date(text: str, reference: datetime) -> datetime | None:
    if "pasado manana" in text:
        return reference + timedelta(days=2)

    if _has_tomorrow(text):
        return reference + timedelta(days=1)

    if re.search(r"\bhoy\b", text):
        return reference

    match = RELATIVE_DAYS_RE.search(text)
    if match:
        days = int(match.group(1))
        if 0 <= days <= 60:
            return reference + timedelta(days=days)
    return None


def _parse_weekday(text: str, reference: datetime) -> datetime | None:
    for name, weekday in WEEKDAYS.items():
        if re.search(rf"\b(?:el\s+|proximo\s+|proxima\s+)?{name}\b", text):
            days_ahead = (weekday - reference.weekday()) % 7
            if days_ahead == 0 or f"proximo {name}" in text or f"proxima {name}" in text:
                days_ahead = 7 if days_ahead == 0 else days_ahead
            return reference + timedelta(days=days_ahead)
    return None


def _extract_time(text: str) -> tuple[int, int] | None:
    match = TIME_COLON_RE.search(text)
    if match:
        hour = int(match.group(1))
        minute = int(match.group(2))
        suffix = match.group(3)
        return _normalize_hour(hour, minute, suffix)

    match = TIME_COMPACT_RE.search(text)
    if match:
        return _normalize_hour(int(match.group(1)), 0, match.group(2))

    match = TIME_HOUR_RE.search(text)
    if match:
        hour = int(match.group(1))
        suffix = match.group(2)
        if suffix == "tarde" and hour < 12:
            hour += 12
        elif suffix == "noche" and hour < 12:
            hour += 12
        return _normalize_hour(hour, 0, None)

    return None


def _normalize_hour(hour: int, minute: int, suffix: str | None) -> tuple[int, int] | None:
    if not (0 <= minute <= 59):
        return None
    if suffix == "pm" and hour < 12:
        hour += 12
    if suffix == "am" and hour == 12:
        hour = 0
    if not (0 <= hour <= 23):
        return None
    return hour, minute


def _daypart_time(text: str) -> tuple[int, int] | None:
    if "en la tarde" in text or "por la tarde" in text:
        return 15, 0
    if "en la noche" in text or "por la noche" in text:
        return 19, 0
    if "en la manana" in text or "por la manana" in text:
        return 9, 0
    return None


def _has_tomorrow(text: str) -> bool:
    if "manana" not in text:
        return False
    if "en la manana" in text or "por la manana" in text:
        return False
    return True


def _format_if_valid(candidate: datetime | None, reference: datetime) -> str | None:
    if candidate is None:
        return None
    if candidate.tzinfo is None:
        candidate = candidate.replace(tzinfo=BOGOTA_TZ)
    if candidate < reference - timedelta(hours=1):
        return None
    return candidate.strftime("%Y-%m-%dT%H:%M")


def _safe_datetime(year: int, month: int, day: int, hour: int, minute: int) -> datetime | None:
    try:
        return datetime(year, month, day, hour, minute, tzinfo=BOGOTA_TZ)
    except ValueError:
        return None


def _normalize(text: str) -> str:
    decomposed = unicodedata.normalize("NFKD", text)
    ascii_text = "".join(char for char in decomposed if not unicodedata.combining(char))
    lowered = ascii_text.lower()
    lowered = re.sub(r"[!?,.;(){}\[\]]", " ", lowered)
    return re.sub(r"\s+", " ", lowered).strip()
