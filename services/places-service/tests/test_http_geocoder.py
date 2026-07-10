from __future__ import annotations

import json

import httpx
import pytest

from places_service.adapters.outbound.geocoding.provider import (
    HttpGeocoder,
    InMemoryAttemptRecorder,
    sanitize_payload,
)


def _geocoder(**kwargs) -> HttpGeocoder:
    sleeps: list[float] = []

    def fake_sleep(seconds: float) -> None:
        sleeps.append(seconds)

    recorder = kwargs.pop("attempt_recorder", InMemoryAttemptRecorder())
    g = HttpGeocoder(
        sleep=fake_sleep,
        clock=lambda: 1000.0,
        now=lambda: "2026-07-09T00:00:00+00:00",
        attempt_recorder=recorder,
        **kwargs,
    )
    g._sleeps = sleeps  # type: ignore[attr-defined]
    return g


def test_sanitize_payload_strips_secrets() -> None:
    cleaned = sanitize_payload({"api_key": "secret", "lat": 1, "Authorization": "Bearer x"})
    assert cleaned["api_key"] == "***"
    assert cleaned["Authorization"] == "***"
    assert cleaned["lat"] == 1


def test_http_geocoder_success(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("PLACES_GEOCODING_API_URL", "https://geo.test/search")
    monkeypatch.setenv("PLACES_GEOCODING_RETRIES", "1")
    monkeypatch.setenv("PLACES_GEOCODING_MIN_CONFIDENCE", "0.5")

    def handler(request: httpx.Request) -> httpx.Response:
        assert "api_key" not in str(request.url)
        return httpx.Response(
            200,
            json=[{"lat": "7.1193", "lon": "-73.1227", "importance": 0.9, "place_id": "p1"}],
        )

    recorder = InMemoryAttemptRecorder()
    geo = _geocoder(transport=httpx.MockTransport(handler), attempt_recorder=recorder)
    result = geo.geocode("Calle 36 Bucaramanga", site_id="site-1")
    assert result.status == "success"
    assert result.lat == pytest.approx(7.1193)
    assert len(result.attempts) == 1
    assert result.attempts[0].status == "success"
    assert result.attempts[0].http_status == 200
    assert result.attempts[0].provider_record_id == "p1"
    assert len(recorder.attempts) == 1
    payload = json.loads(result.attempts[0].response_payload or "{}")
    assert "api_key" not in payload


def test_http_geocoder_timeout_retries(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("PLACES_GEOCODING_API_URL", "https://geo.test/search")
    monkeypatch.setenv("PLACES_GEOCODING_RETRIES", "3")
    calls = {"n": 0}

    def handler(request: httpx.Request) -> httpx.Response:
        calls["n"] += 1
        raise httpx.ReadTimeout("timed out")

    geo = _geocoder(transport=httpx.MockTransport(handler))
    result = geo.geocode("q", site_id="site-t")
    assert result.status == "timeout"
    assert len(result.attempts) == 3
    assert all(a.status == "timeout" for a in result.attempts)
    assert geo._sleeps  # type: ignore[attr-defined]
    assert calls["n"] == 3


def test_http_geocoder_rate_limited(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("PLACES_GEOCODING_API_URL", "https://geo.test/search")
    monkeypatch.setenv("PLACES_GEOCODING_RETRIES", "2")

    def handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(429, text="slow down")

    geo = _geocoder(transport=httpx.MockTransport(handler))
    result = geo.geocode("q")
    assert result.status == "rate_limited"
    assert all(a.status == "rate_limited" for a in result.attempts)


def test_http_geocoder_provider_5xx(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("PLACES_GEOCODING_API_URL", "https://geo.test/search")
    monkeypatch.setenv("PLACES_GEOCODING_RETRIES", "2")

    def handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(500, text="boom")

    geo = _geocoder(transport=httpx.MockTransport(handler))
    result = geo.geocode("q")
    assert result.status == "provider_5xx"
    assert result.attempts[0].http_status == 500


def test_http_geocoder_empty_result(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("PLACES_GEOCODING_API_URL", "https://geo.test/search")

    def handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(200, json=[])

    geo = _geocoder(transport=httpx.MockTransport(handler))
    result = geo.geocode("q")
    assert result.status == "empty_result"


def test_http_geocoder_outside_colombia(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("PLACES_GEOCODING_API_URL", "https://geo.test/search")

    def handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(200, json=[{"lat": "40.7", "lon": "-74.0", "importance": 0.9}])

    geo = _geocoder(transport=httpx.MockTransport(handler))
    result = geo.geocode("nyc")
    assert result.status == "outside_colombia"
    assert result.lat is None


def test_http_geocoder_low_confidence(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("PLACES_GEOCODING_API_URL", "https://geo.test/search")
    monkeypatch.setenv("PLACES_GEOCODING_MIN_CONFIDENCE", "0.8")

    def handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(
            200,
            json=[{"lat": "7.1193", "lon": "-73.1227", "importance": 0.2}],
        )

    geo = _geocoder(transport=httpx.MockTransport(handler))
    result = geo.geocode("q", site_id="site-low")
    assert result.status == "low_confidence"
    assert result.lat == pytest.approx(7.1193)
    assert result.attempts[0].status == "low_confidence"
