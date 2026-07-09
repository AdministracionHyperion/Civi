from __future__ import annotations

"""Geocoding adapter — disabled by default; no external calls in tests/local."""

import os
from dataclasses import dataclass
from typing import Protocol


@dataclass
class GeocodeResult:
    lat: float | None
    lng: float | None
    confidence: float | None
    precision: str
    provider: str
    status: str
    query: str
    error: str | None = None


class Geocoder(Protocol):
    def geocode(self, query: str) -> GeocodeResult:
        ...


class DisabledGeocoder:
    def geocode(self, query: str) -> GeocodeResult:
        return GeocodeResult(
            lat=None,
            lng=None,
            confidence=None,
            precision="unknown",
            provider="disabled",
            status="not_attempted",
            query=query,
            error="geocoding disabled",
        )


def geocoder_from_env() -> Geocoder:
    mode = os.getenv("PLACES_GEOCODING_MODE", "disabled").strip().lower()
    if mode in {"", "disabled", "off", "none", "manual_import", "http"}:
        # http intentionally not auto-enabled without an explicit future adapter + key
        return DisabledGeocoder()
    return DisabledGeocoder()
