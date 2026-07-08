from __future__ import annotations

from datetime import datetime

from bot_orchestrator.shared.date_parser import BOGOTA_TZ, parse_natural_datetime


REFERENCE = datetime(2026, 7, 7, 12, 0, tzinfo=BOGOTA_TZ)


def test_parse_tomorrow_and_dayparts() -> None:
    assert parse_natural_datetime("manana a las 10", now=REFERENCE) == "2026-07-08T10:00"
    assert parse_natural_datetime("manana en la tarde", now=REFERENCE) == "2026-07-08T15:00"
    assert parse_natural_datetime("pasado manana 9:30", now=REFERENCE) == "2026-07-09T09:30"


def test_parse_weekday_prefers_future() -> None:
    assert parse_natural_datetime("el jueves a las 9am", now=REFERENCE) == "2026-07-09T09:00"
    assert parse_natural_datetime("el viernes", now=REFERENCE) == "2026-07-10T09:00"
    assert parse_natural_datetime("el proximo lunes a las 10am", now=REFERENCE) == "2026-07-13T10:00"


def test_parse_relative_and_explicit_dates() -> None:
    assert parse_natural_datetime("en 3 dias a las 8", now=REFERENCE) == "2026-07-10T08:00"
    assert parse_natural_datetime("2026-07-10 09:00", now=REFERENCE) == "2026-07-10T09:00"
    assert parse_natural_datetime("10/07/2026 09:30", now=REFERENCE) == "2026-07-10T09:30"
    assert parse_natural_datetime("10 de julio a las 3pm", now=REFERENCE) == "2026-07-10T15:00"


def test_parse_rejects_past_or_unparseable_dates() -> None:
    assert parse_natural_datetime("2026-01-01 09:00", now=REFERENCE) is None
    assert parse_natural_datetime("cuando puedas", now=REFERENCE) is None
