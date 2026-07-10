"""Generate http_geocoding_attempts_report.json via MockTransport (no network)."""

from __future__ import annotations

import json
import os
from pathlib import Path

import httpx

from places_service.adapters.outbound.geocoding.provider import (
    HttpGeocoder,
    InMemoryAttemptRecorder,
    sanitize_payload,
)

ROOT = Path(__file__).resolve().parents[2]
REPORT = (
    ROOT
    / "services"
    / "places-service"
    / "data"
    / "reports"
    / "http_geocoding_attempts_report.json"
)


def _run(handler, **env):
    for key, value in env.items():
        os.environ[key] = str(value)
    sleeps: list[float] = []
    recorder = InMemoryAttemptRecorder()
    geocoder = HttpGeocoder(
        sleep=lambda s: sleeps.append(s),
        clock=lambda: 1000.0,
        now=lambda: "2026-07-09T00:00:00+00:00",
        attempt_recorder=recorder,
        transport=httpx.MockTransport(handler),
    )
    return geocoder, recorder


def main() -> int:
    cases: list[dict] = []

    def h_ok(_req: httpx.Request) -> httpx.Response:
        return httpx.Response(
            200,
            json=[{"lat": "7.1193", "lon": "-73.1227", "importance": 0.9, "place_id": "p1"}],
        )

    geo, _ = _run(
        h_ok,
        PLACES_GEOCODING_API_URL="https://geo.test/search",
        PLACES_GEOCODING_RETRIES="1",
        PLACES_GEOCODING_MIN_CONFIDENCE="0.5",
    )
    result = geo.geocode("Calle 36", site_id="s1")
    cases.append(
        {
            "case": "success_first_attempt",
            "status": result.status,
            "attempts": len(result.attempts),
            "passed": result.status == "success" and len(result.attempts) == 1,
        }
    )

    def h_to(_req: httpx.Request) -> httpx.Response:
        raise httpx.ReadTimeout("t")

    geo, _ = _run(
        h_to,
        PLACES_GEOCODING_API_URL="https://geo.test/search",
        PLACES_GEOCODING_RETRIES="3",
    )
    result = geo.geocode("q", site_id="s2")
    cases.append(
        {
            "case": "timeout_all_retries",
            "status": result.status,
            "attempts": len(result.attempts),
            "passed": result.status == "timeout" and len(result.attempts) == 3,
        }
    )

    calls = {"n": 0}

    def h_429(_req: httpx.Request) -> httpx.Response:
        calls["n"] += 1
        if calls["n"] < 2:
            return httpx.Response(429, json={"error": "rate"})
        return httpx.Response(
            200,
            json=[{"lat": "7.1", "lon": "-73.1", "importance": 0.8, "place_id": "p2"}],
        )

    geo, _ = _run(
        h_429,
        PLACES_GEOCODING_API_URL="https://geo.test/search",
        PLACES_GEOCODING_RETRIES="3",
        PLACES_GEOCODING_MIN_CONFIDENCE="0.5",
    )
    result = geo.geocode("q", site_id="s3")
    cases.append(
        {
            "case": "rate_limited_then_success",
            "status": result.status,
            "attempts": len(result.attempts),
            "statuses": [a.status for a in result.attempts],
            "passed": result.status == "success" and len(result.attempts) >= 2,
        }
    )

    def h_500(_req: httpx.Request) -> httpx.Response:
        return httpx.Response(500, json={"error": "x"})

    geo, _ = _run(
        h_500,
        PLACES_GEOCODING_API_URL="https://geo.test/search",
        PLACES_GEOCODING_RETRIES="2",
    )
    result = geo.geocode("q", site_id="s4")
    cases.append(
        {
            "case": "provider_5xx",
            "status": result.status,
            "attempts": len(result.attempts),
            "passed": len(result.attempts) >= 2
            and all(a.http_status == 500 for a in result.attempts),
        }
    )

    def h_out(_req: httpx.Request) -> httpx.Response:
        return httpx.Response(
            200,
            json=[{"lat": "40.7", "lon": "-74.0", "importance": 0.9, "place_id": "ny"}],
        )

    geo, _ = _run(
        h_out,
        PLACES_GEOCODING_API_URL="https://geo.test/search",
        PLACES_GEOCODING_RETRIES="1",
        PLACES_GEOCODING_MIN_CONFIDENCE="0.5",
    )
    result = geo.geocode("q", site_id="s5")
    cases.append(
        {
            "case": "outside_colombia",
            "status": result.status,
            "attempts": len(result.attempts),
            "passed": result.status in ("outside_colombia", "failed")
            and len(result.attempts) == 1,
        }
    )

    def h_low(_req: httpx.Request) -> httpx.Response:
        return httpx.Response(
            200,
            json=[{"lat": "7.1", "lon": "-73.1", "importance": 0.1, "place_id": "low"}],
        )

    geo, _ = _run(
        h_low,
        PLACES_GEOCODING_API_URL="https://geo.test/search",
        PLACES_GEOCODING_RETRIES="1",
        PLACES_GEOCODING_MIN_CONFIDENCE="0.5",
    )
    result = geo.geocode("q", site_id="s6")
    cases.append(
        {
            "case": "low_confidence",
            "status": result.status,
            "attempts": len(result.attempts),
            "passed": result.status == "low_confidence",
        }
    )

    cleaned = sanitize_payload({"api_key": "secret", "Authorization": "Bearer x", "lat": 1})
    cases.append(
        {
            "case": "sanitize_no_secrets",
            "passed": cleaned.get("api_key") == "***" and cleaned.get("Authorization") == "***",
        }
    )

    report = {
        "generator": "scripts/places-catalog/generate_http_attempts_report.py",
        "total_attempts_persisted_across_cases": sum(
            int(c.get("attempts", 0)) for c in cases if "attempts" in c
        ),
        "cases": cases,
        "passed": all(bool(c.get("passed")) for c in cases),
        "secrets_persisted": False,
    }
    REPORT.parent.mkdir(parents=True, exist_ok=True)
    REPORT.write_text(json.dumps(report, ensure_ascii=False, indent=2), encoding="utf-8")
    print(json.dumps({"path": str(REPORT), "passed": report["passed"]}, indent=2))
    return 0 if report["passed"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
