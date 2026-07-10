"""Compose smoke gate for places + appointment production hardening paths.

Covers nearest error codes, GPS ordering/radius, booking eligibility,
appointment 422/201/503, and a channel→bot→places hop.

Seed MUST succeed; F/G cases never pass as skipped.
"""

from __future__ import annotations

import json
import os
import subprocess
import sys
import time
import urllib.error
import urllib.request
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
COMPOSE_FILE = ROOT / "infra" / "docker-compose.local.yml"
REPORT = (
    ROOT
    / "services"
    / "places-service"
    / "data"
    / "reports"
    / "compose_smoke_report.json"
)

TOKEN = os.environ.get("INTERNAL_SERVICE_TOKEN", "change-me-local-only")
PLACES_URL = os.environ.get("PLACES_SMOKE_URL", "http://127.0.0.1:8085")
APPOINTMENT_URL = os.environ.get("APPOINTMENT_SMOKE_URL", "http://127.0.0.1:8086")
BOT_URL = os.environ.get("BOT_SMOKE_URL", "http://127.0.0.1:8082")
CONVERSATION_URL = os.environ.get("CONVERSATION_SMOKE_URL", "http://127.0.0.1:8081")
CHANNEL_URL = os.environ.get("CHANNEL_SMOKE_URL", "http://127.0.0.1:8080")
COMPOSE = ["docker", "compose", "-f", str(COMPOSE_FILE)]

CORE_INFRA = ["postgres", "redis", "notification-service"]
CORE_APPS = [
    "places-service",
    "appointment-service",
    "bot-orchestrator",
    "conversation-service",
    "channel-gateway",
]
HEALTH_TARGETS = {
    "places-service": (PLACES_URL, 8085),
    "appointment-service": (APPOINTMENT_URL, 8086),
    "bot-orchestrator": (BOT_URL, 8082),
    "conversation-service": (CONVERSATION_URL, 8081),
    "channel-gateway": (CHANNEL_URL, 8080),
}

REQUIRED_CASES = [
    "A_city_or_coordinates_required",
    "B_no_coverage_in_municipality",
    "C_coordinates_outside_colombia",
    "E_booking_eligibility_missing",
    "F_gps_ordering",
    "G_appointment_422_non_bookable",
    "G_appointment_201_bookable",
    "H_appointment_503_places_down",
    "I_channel_bot_places_hop",
]


def _run(cmd: list[str], *, check: bool = True, env: dict | None = None) -> subprocess.CompletedProcess:
    return subprocess.run(
        cmd,
        cwd=str(ROOT),
        check=check,
        text=True,
        capture_output=True,
        env=env,
    )


def _http_json(
    method: str,
    url: str,
    *,
    body: dict | None = None,
    token: str | None = TOKEN,
    timeout: float = 15.0,
) -> tuple[int, dict | list | str, float]:
    data = None
    headers = {"Accept": "application/json"}
    if token:
        headers["Authorization"] = f"Bearer {token}"
    if body is not None:
        data = json.dumps(body).encode("utf-8")
        headers["Content-Type"] = "application/json"
    req = urllib.request.Request(url, data=data, headers=headers, method=method)
    started = time.perf_counter()
    try:
        with urllib.request.urlopen(req, timeout=timeout) as resp:
            raw = resp.read().decode("utf-8")
            elapsed_ms = round((time.perf_counter() - started) * 1000, 2)
            try:
                return resp.status, json.loads(raw) if raw else {}, elapsed_ms
            except json.JSONDecodeError:
                return resp.status, raw, elapsed_ms
    except urllib.error.HTTPError as exc:
        raw = exc.read().decode("utf-8")
        elapsed_ms = round((time.perf_counter() - started) * 1000, 2)
        try:
            payload = json.loads(raw) if raw else {}
        except json.JSONDecodeError:
            payload = raw
        return exc.code, payload, elapsed_ms


def _hop(
    *,
    service: str,
    endpoint: str,
    method: str,
    url: str,
    expected: object,
    actual: object,
    passed: bool,
    elapsed_ms: float,
    status: int,
) -> dict:
    return {
        "service": service,
        "endpoint": endpoint,
        "method": method,
        "url": url,
        "HTTP status": status,
        "elapsed_ms": elapsed_ms,
        "expected": expected,
        "actual": actual,
        "passed": passed,
    }


def _wait_health(base: str, *, timeout_s: int = 180) -> None:
    deadline = time.time() + timeout_s
    last_err = ""
    while time.time() < deadline:
        ok = True
        for path in ("/health/live", "/health/ready"):
            try:
                status, _, _ = _http_json("GET", f"{base}{path}", token=None, timeout=5.0)
                if status != 200:
                    ok = False
                    last_err = f"{base}{path} -> {status}"
                    break
            except Exception as exc:  # noqa: BLE001
                ok = False
                last_err = str(exc)
                break
        if ok:
            return
        time.sleep(2)
    raise RuntimeError(f"health timeout for {base}: {last_err}")


def _seed_places_sql() -> dict:
    """Seed GPS + bookable/non-bookable + out-of-radius fixtures into places DB."""
    ts = "2026-07-09T00:00:00+00:00"
    sql = f"""
    INSERT INTO places_entities (
      entity_id, document_type, document_number, document_valid, document_validation_status,
      legal_name, legal_name_normalized, entity_status, requires_manual_review, created_at, updated_at
    ) VALUES
    ('ent-smoke-1', 'NIT', '800197268', true, 'valid_with_dv', 'CDA Smoke Near', 'CDA SMOKE NEAR', 'unknown', false, '{ts}', '{ts}'),
    ('ent-smoke-2', 'NIT', '800197269', true, 'valid_with_dv', 'CDA Smoke Far', 'CDA SMOKE FAR', 'unknown', false, '{ts}', '{ts}'),
    ('ent-smoke-3', 'NIT', '800197270', false, 'invalid', 'CDA Smoke Nobook', 'CDA SMOKE NOBOOK', 'unknown', true, '{ts}', '{ts}'),
    ('ent-smoke-4', 'NIT', '800197271', true, 'valid_with_dv', 'CDA Smoke Bogota', 'CDA SMOKE BOGOTA', 'unknown', false, '{ts}', '{ts}')
    ON CONFLICT (entity_id) DO NOTHING;

    INSERT INTO places_sites (
      site_id, entity_id, actor_type, name, name_normalized,
      address_raw, address_normalized, address_quality,
      department, municipality, raw_city, raw_department, municipality_code,
      lat, lng, geocode_status, location_precision,
      operational_status, status_verified, status_inferred_from_name,
      is_official_actor, is_partner, is_bookable, booking_mode,
      quality_score, requires_manual_review,
      snapshot_presence, source_presence_status, present_in_latest_snapshot,
      created_at, updated_at
    ) VALUES
    (
      'smoke-near-01', 'ent-smoke-1', 'CDA', 'CDA Smoke Near', 'CDA SMOKE NEAR',
      'Calle 36', 'CALLE 36', 'valid',
      'Santander', 'Bucaramanga', 'Bucaramanga', 'Santander', '68001',
      7.1193, -73.1227, 'ok', 'address',
      'unknown', false, false,
      true, true, true, 'civi',
      0.9, false,
      'present', 'present', true,
      '{ts}', '{ts}'
    ),
    (
      'smoke-far-01', 'ent-smoke-2', 'CDA', 'CDA Smoke Far', 'CDA SMOKE FAR',
      'Calle 100', 'CALLE 100', 'valid',
      'Santander', 'Bucaramanga', 'Bucaramanga', 'Santander', '68001',
      7.1500, -73.1500, 'ok', 'address',
      'unknown', false, false,
      true, true, true, 'civi',
      0.8, false,
      'present', 'present', true,
      '{ts}', '{ts}'
    ),
    (
      'smoke-nobook-01', 'ent-smoke-3', 'CDA', 'CDA Smoke Nobook', 'CDA SMOKE NOBOOK',
      'Calle 50', 'CALLE 50', 'valid',
      'Santander', 'Bucaramanga', 'Bucaramanga', 'Santander', '68001',
      7.1200, -73.1230, 'ok', 'address',
      'unknown', false, false,
      true, true, false, 'information_only',
      0.5, true,
      'present', 'present', true,
      '{ts}', '{ts}'
    ),
    (
      'smoke-bogota-01', 'ent-smoke-4', 'CDA', 'CDA Smoke Bogota', 'CDA SMOKE BOGOTA',
      'Calle 26', 'CALLE 26', 'valid',
      'Bogota D.C.', 'Bogota', 'Bogota', 'Bogota D.C.', '11001',
      4.6097, -74.0817, 'ok', 'address',
      'unknown', false, false,
      true, true, true, 'civi',
      0.85, false,
      'present', 'present', true,
      '{ts}', '{ts}'
    )
    ON CONFLICT (site_id) DO UPDATE SET
      lat = EXCLUDED.lat,
      lng = EXCLUDED.lng,
      is_partner = EXCLUDED.is_partner,
      is_bookable = EXCLUDED.is_bookable,
      booking_mode = EXCLUDED.booking_mode,
      source_presence_status = EXCLUDED.source_presence_status,
      present_in_latest_snapshot = EXCLUDED.present_in_latest_snapshot;

    -- Bookable smoke sites need ops_whatsapp after partner-notify gate
    INSERT INTO places_contacts (
      contact_id, site_id, contact_type, value_raw, value_normalized, e164,
      is_valid, is_public, source_record_id
    ) VALUES
    (
      'ops-smoke-near-01', 'smoke-near-01', 'ops_whatsapp',
      '+573001112201', '573001112201', '573001112201',
      true, false, NULL
    ),
    (
      'ops-smoke-far-01', 'smoke-far-01', 'ops_whatsapp',
      '+573001112202', '573001112202', '573001112202',
      true, false, NULL
    )
    ON CONFLICT (contact_id) DO UPDATE SET
      e164 = EXCLUDED.e164,
      value_normalized = EXCLUDED.value_normalized,
      value_raw = EXCLUDED.value_raw,
      is_valid = EXCLUDED.is_valid;
    """
    ps = _run([*COMPOSE, "ps", "-q", "postgres"], check=False)
    container = (ps.stdout or "").strip().splitlines()
    if not container:
        raise RuntimeError("postgres container not found")
    proc = subprocess.run(
        ["docker", "exec", "-i", container[0], "psql", "-U", "civi", "-d", "civi", "-v", "ON_ERROR_STOP=1"],
        input=sql,
        cwd=str(ROOT),
        text=True,
        capture_output=True,
        check=False,
    )
    if proc.returncode != 0:
        raise RuntimeError(f"seed sql failed: {proc.stderr or proc.stdout}")
    return {
        "seeded": True,
        "sites": ["smoke-near-01", "smoke-far-01", "smoke-nobook-01", "smoke-bogota-01"],
        "ops_contacts": ["smoke-near-01", "smoke-far-01"],
    }


def main() -> int:
    report: dict = {
        "steps": [],
        "cases": {},
        "hops": [],
        "passed": False,
        "notes": {
            "gps_ordering_unit_tests": "services/places-service/tests/test_catalog_pipeline.py",
            "appointment_422_503_unit_tests": "services/appointment-service/tests/test_appointment_service.py",
            "channel_path": (
                "channel-gateway + conversation health, then bot-orchestrator "
                "/internal/agent/turns → places.find_nearest"
            ),
        },
    }
    env = os.environ.copy()
    env.setdefault("INTERNAL_SERVICE_TOKEN", TOKEN)
    env.setdefault("WHATSAPP_VERIFY_TOKEN", "change-me-local-only")
    env.setdefault("EVENT_PUBLISHER_MODE", "disabled")
    env.setdefault("LLM_PROVIDER_MODE", "disabled")
    env.setdefault("WHATSAPP_PROVIDER_MODE", "disabled")

    try:
        cfg = _run([*COMPOSE, "config", "--quiet"], env=env)
        report["steps"].append({"compose_config": "ok", "rc": cfg.returncode})

        _run([*COMPOSE, "up", "-d", "--build", *CORE_INFRA], env=env)
        report["steps"].append({"up_infra": CORE_INFRA})
        _run([*COMPOSE, "up", "-d", "--build", "--no-deps", *CORE_APPS], env=env)
        report["steps"].append({"up_apps": CORE_APPS})

        for name, (base, _port) in HEALTH_TARGETS.items():
            _wait_health(base)
            report["steps"].append({f"health_{name}": "ok"})

        # A) nearest no city
        url = f"{PLACES_URL}/internal/places/nearest"
        status, body, elapsed = _http_json(
            "POST",
            url,
            body={"procedure": "tecnomecanica", "limit": 5},
        )
        reason = (body or {}).get("no_results_reason") if isinstance(body, dict) else None
        passed = status == 200 and reason == "city_or_coordinates_required"
        report["cases"]["A_city_or_coordinates_required"] = {
            "status": status,
            "no_results_reason": reason,
            "passed": passed,
        }
        report["hops"].append(
            _hop(
                service="places-service",
                endpoint="/internal/places/nearest",
                method="POST",
                url=url,
                expected={"status": 200, "no_results_reason": "city_or_coordinates_required"},
                actual={"status": status, "no_results_reason": reason},
                passed=passed,
                elapsed_ms=elapsed,
                status=status,
            )
        )

        # B) fake city
        status, body, elapsed = _http_json(
            "POST",
            url,
            body={"procedure": "tecnomecanica", "city": "CiudadInventadaXYZ", "limit": 5},
        )
        reason = (body or {}).get("no_results_reason") if isinstance(body, dict) else None
        passed = status == 200 and reason == "no_coverage_in_municipality"
        report["cases"]["B_no_coverage_in_municipality"] = {
            "status": status,
            "no_results_reason": reason,
            "passed": passed,
        }
        report["hops"].append(
            _hop(
                service="places-service",
                endpoint="/internal/places/nearest",
                method="POST",
                url=url,
                expected={"status": 200, "no_results_reason": "no_coverage_in_municipality"},
                actual={"status": status, "no_results_reason": reason},
                passed=passed,
                elapsed_ms=elapsed,
                status=status,
            )
        )

        # C) outside Colombia
        status, body, elapsed = _http_json(
            "POST",
            url,
            body={"procedure": "tecnomecanica", "lat": 40.7128, "lng": -74.0060, "limit": 5},
        )
        reason = (body or {}).get("no_results_reason") if isinstance(body, dict) else None
        passed = status == 200 and reason == "coordinates_outside_colombia"
        report["cases"]["C_coordinates_outside_colombia"] = {
            "status": status,
            "no_results_reason": reason,
            "passed": passed,
        }
        report["hops"].append(
            _hop(
                service="places-service",
                endpoint="/internal/places/nearest",
                method="POST",
                url=url,
                expected={"status": 200, "no_results_reason": "coordinates_outside_colombia"},
                actual={"status": status, "no_results_reason": reason},
                passed=passed,
                elapsed_ms=elapsed,
                status=status,
            )
        )

        # Seed is mandatory for F/G — failure fails the whole gate
        seed_info = _seed_places_sql()
        report["steps"].append({"seed": seed_info})

        # E) booking eligibility missing site
        elig_url = f"{PLACES_URL}/internal/places/does-not-exist-smoke/booking-eligibility"
        status, body, elapsed = _http_json("GET", elig_url)
        elig_reason = (body or {}).get("eligibility_reason") if isinstance(body, dict) else None
        exists = (body or {}).get("exists") if isinstance(body, dict) else None
        passed = status == 200 and exists is False
        report["cases"]["E_booking_eligibility_missing"] = {
            "status": status,
            "exists": exists,
            "eligibility_reason": elig_reason,
            "passed": passed,
        }
        report["hops"].append(
            _hop(
                service="places-service",
                endpoint="/internal/places/{id}/booking-eligibility",
                method="GET",
                url=elig_url,
                expected={"status": 200, "exists": False},
                actual={"status": status, "exists": exists},
                passed=passed,
                elapsed_ms=elapsed,
                status=status,
            )
        )

        # F) GPS ordering + out-of-radius exclusion + distance ordering
        status, body, elapsed = _http_json(
            "POST",
            url,
            body={
                "procedure": "tecnomecanica",
                "lat": 7.1193,
                "lng": -73.1227,
                "limit": 10,
            },
        )
        places = (body or {}).get("places") if isinstance(body, dict) else []
        if not isinstance(places, list):
            places = []
        ids = [p.get("id") for p in places]
        by_id = {p.get("id"): p for p in places if isinstance(p, dict)}
        near = by_id.get("smoke-near-01") or {}
        far = by_id.get("smoke-far-01") or {}
        near_dist = near.get("distance_km")
        far_dist = far.get("distance_km")
        ordering_ok = (
            "smoke-near-01" in ids
            and "smoke-far-01" in ids
            and ids.index("smoke-near-01") < ids.index("smoke-far-01")
            and near_dist is not None
            and far_dist is not None
            and float(near_dist) < float(far_dist)
        )
        out_of_radius_ok = "smoke-bogota-01" not in ids
        passed_f = status == 200 and ordering_ok and out_of_radius_ok
        report["cases"]["F_gps_ordering"] = {
            "status": status,
            "ids": ids,
            "near_distance_km": near_dist,
            "far_distance_km": far_dist,
            "bogota_excluded": out_of_radius_ok,
            "passed": passed_f,
        }
        report["hops"].append(
            _hop(
                service="places-service",
                endpoint="/internal/places/nearest",
                method="POST",
                url=url,
                expected={
                    "status": 200,
                    "near_before_far": True,
                    "near_dist_lt_far": True,
                    "bogota_excluded": True,
                },
                actual={
                    "status": status,
                    "ids": ids,
                    "near_distance_km": near_dist,
                    "far_distance_km": far_dist,
                    "bogota_excluded": out_of_radius_ok,
                },
                passed=passed_f,
                elapsed_ms=elapsed,
                status=status,
            )
        )

        # G422) appointment non-bookable
        appt_url = f"{APPOINTMENT_URL}/internal/appointments"
        status, body, elapsed = _http_json(
            "POST",
            appt_url,
            body={
                "user_key": "smoke-user-422",
                "procedure": "tecnomecanica",
                "starts_at": "2026-08-01T10:00:00",
                "place": {
                    "id": "smoke-nobook-01",
                    "name": "CDA Smoke Nobook",
                    "address": "Calle 50",
                    "city": "Bucaramanga",
                },
            },
        )
        detail = body.get("detail") if isinstance(body, dict) else body
        passed = status == 422
        report["cases"]["G_appointment_422_non_bookable"] = {
            "status": status,
            "detail": detail,
            "passed": passed,
        }
        report["hops"].append(
            _hop(
                service="appointment-service",
                endpoint="/internal/appointments",
                method="POST",
                url=appt_url,
                expected={"status": 422},
                actual={"status": status, "detail": detail},
                passed=passed,
                elapsed_ms=elapsed,
                status=status,
            )
        )

        # G201) appointment bookable success
        status, body, elapsed = _http_json(
            "POST",
            appt_url,
            body={
                "user_key": "smoke-user-201",
                "procedure": "tecnomecanica",
                "starts_at": "2026-08-01T10:30:00",
                "place": {
                    "id": "smoke-near-01",
                    "name": "CDA Smoke Near",
                    "address": "Calle 36",
                    "city": "Bucaramanga",
                },
            },
        )
        passed = status == 201
        report["cases"]["G_appointment_201_bookable"] = {
            "status": status,
            "body": body if isinstance(body, dict) else str(body)[:200],
            "passed": passed,
        }
        report["hops"].append(
            _hop(
                service="appointment-service",
                endpoint="/internal/appointments",
                method="POST",
                url=appt_url,
                expected={"status": 201},
                actual={"status": status},
                passed=passed,
                elapsed_ms=elapsed,
                status=status,
            )
        )

        # I) channel → conversation health + bot turn that touches places
        channel_live = f"{CHANNEL_URL}/health/live"
        conv_live = f"{CONVERSATION_URL}/health/live"
        bot_turn = f"{BOT_URL}/internal/agent/turns"
        ch_status, _, ch_elapsed = _http_json("GET", channel_live, token=None)
        cv_status, _, cv_elapsed = _http_json("GET", conv_live, token=None)
        bot_status, bot_body, bot_elapsed = _http_json(
            "POST",
            bot_turn,
            body={
                "user_key": "smoke-channel-user",
                "channel": "web",
                "text": "quiero agendar tecnomecanica en Bucaramanga el 2026-08-15 09:00",
            },
            timeout=30.0,
        )
        tool_calls = bot_body.get("tool_calls") if isinstance(bot_body, dict) else None
        bot_mode = bot_body.get("mode") if isinstance(bot_body, dict) else None
        places_touched = isinstance(tool_calls, list) and "places.find_nearest" in tool_calls
        passed_i = (
            ch_status == 200
            and cv_status == 200
            and bot_status == 200
            and places_touched
        )
        report["cases"]["I_channel_bot_places_hop"] = {
            "channel_health": ch_status,
            "conversation_health": cv_status,
            "bot_status": bot_status,
            "bot_mode": bot_mode,
            "tool_calls": tool_calls,
            "passed": passed_i,
        }
        report["hops"].extend(
            [
                _hop(
                    service="channel-gateway",
                    endpoint="/health/live",
                    method="GET",
                    url=channel_live,
                    expected={"status": 200},
                    actual={"status": ch_status},
                    passed=ch_status == 200,
                    elapsed_ms=ch_elapsed,
                    status=ch_status,
                ),
                _hop(
                    service="conversation-service",
                    endpoint="/health/live",
                    method="GET",
                    url=conv_live,
                    expected={"status": 200},
                    actual={"status": cv_status},
                    passed=cv_status == 200,
                    elapsed_ms=cv_elapsed,
                    status=cv_status,
                ),
                _hop(
                    service="bot-orchestrator",
                    endpoint="/internal/agent/turns",
                    method="POST",
                    url=bot_turn,
                    expected={"status": 200, "tool_calls_contains": "places.find_nearest"},
                    actual={"status": bot_status, "tool_calls": tool_calls, "mode": bot_mode},
                    passed=bot_status == 200 and places_touched,
                    elapsed_ms=bot_elapsed,
                    status=bot_status,
                ),
            ]
        )

        # H) appointment 503 by stopping places-service
        _run([*COMPOSE, "stop", "places-service"], env=env)
        report["steps"].append({"stopped_places_service": True})
        time.sleep(2)
        status, body, elapsed = _http_json(
            "POST",
            appt_url,
            body={
                "user_key": "smoke-user-503",
                "procedure": "tecnomecanica",
                "starts_at": "2026-08-01T11:00:00",
                "place": {
                    "id": "smoke-near-01",
                    "name": "CDA Smoke Near",
                    "address": "Calle 36",
                    "city": "Bucaramanga",
                },
            },
        )
        detail = body.get("detail") if isinstance(body, dict) else body
        passed = status == 503
        report["cases"]["H_appointment_503_places_down"] = {
            "status": status,
            "detail": detail,
            "passed": passed,
        }
        report["hops"].append(
            _hop(
                service="appointment-service",
                endpoint="/internal/appointments",
                method="POST",
                url=appt_url,
                expected={"status": 503},
                actual={"status": status, "detail": detail},
                passed=passed,
                elapsed_ms=elapsed,
                status=status,
            )
        )
        _run([*COMPOSE, "start", "places-service"], env=env)
        _wait_health(PLACES_URL, timeout_s=120)
        report["steps"].append({"restarted_places_service": True})

        report["required_cases"] = REQUIRED_CASES
        report["passed"] = all(report["cases"].get(k, {}).get("passed") for k in REQUIRED_CASES)
        if not report["passed"]:
            report["failed_cases"] = [
                k for k in REQUIRED_CASES if not report["cases"].get(k, {}).get("passed")
            ]
    except Exception as exc:  # noqa: BLE001
        report["passed"] = False
        report["error"] = str(exc)
    finally:
        down = _run([*COMPOSE, "down", "--remove-orphans"], check=False, env=env)
        report["steps"].append({"compose_down": down.returncode})

    REPORT.parent.mkdir(parents=True, exist_ok=True)
    REPORT.write_text(json.dumps(report, ensure_ascii=False, indent=2), encoding="utf-8")
    print(
        json.dumps(
            {
                "passed": report.get("passed"),
                "path": str(REPORT),
                "failed_cases": report.get("failed_cases"),
                "error": report.get("error"),
                "cases": {
                    k: {"passed": (report.get("cases") or {}).get(k, {}).get("passed")}
                    for k in REQUIRED_CASES
                },
            },
            indent=2,
        )
    )
    return 0 if report.get("passed") else 1


if __name__ == "__main__":
    raise SystemExit(main())
