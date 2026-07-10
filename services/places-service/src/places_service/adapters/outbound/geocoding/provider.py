from __future__ import annotations

"""Geocoding adapters — disabled by default; no external calls in tests."""

import csv
import json
import os
import re
import time
from dataclasses import asdict, dataclass, field
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Callable, Protocol
from uuid import uuid4

from civi_common.geo import is_colombia_latlng


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
    site_id: str | None = None
    attempts: list["GeocodeAttemptRecord"] = field(default_factory=list)


@dataclass
class GeocodeAttemptRecord:
    attempt_id: str
    site_id: str | None
    provider: str
    query: str | None
    status: str
    attempt_number: int
    provider_record_id: str | None = None
    http_status: int | None = None
    lat: float | None = None
    lng: float | None = None
    confidence: float | None = None
    precision: str | None = None
    response_payload: str | None = None
    error_code: str | None = None
    error_message: str | None = None
    attempted_at: str = ""
    completed_at: str | None = None


class Geocoder(Protocol):
    def geocode(self, query: str, *, site_id: str | None = None) -> GeocodeResult:
        ...


class AttemptRecorder(Protocol):
    def record(self, attempt: GeocodeAttemptRecord) -> None:
        ...


class InMemoryAttemptRecorder:
    def __init__(self) -> None:
        self.attempts: list[GeocodeAttemptRecord] = []

    def record(self, attempt: GeocodeAttemptRecord) -> None:
        self.attempts.append(attempt)


_SENSITIVE_KEY_RE = re.compile(r"(api[_-]?key|authorization|token|secret|password)", re.I)


def sanitize_payload(payload: Any) -> Any:
    """Strip secrets from provider payloads before persistence."""
    if isinstance(payload, dict):
        cleaned: dict[str, Any] = {}
        for key, value in payload.items():
            if _SENSITIVE_KEY_RE.search(str(key)):
                cleaned[str(key)] = "***"
            else:
                cleaned[str(key)] = sanitize_payload(value)
        return cleaned
    if isinstance(payload, list):
        return [sanitize_payload(item) for item in payload]
    if isinstance(payload, str) and len(payload) > 4000:
        return payload[:4000] + "…"
    return payload


def _utc_now() -> str:
    return datetime.now(timezone.utc).isoformat()


class DisabledGeocoder:
    def geocode(self, query: str, *, site_id: str | None = None) -> GeocodeResult:
        return GeocodeResult(
            lat=None,
            lng=None,
            confidence=None,
            precision="unknown",
            provider="disabled",
            status="not_attempted",
            query=query,
            error="geocoding disabled",
            site_id=site_id,
        )


class ManualImportGeocoder:
    """Loads site_id,lat,lng[,confidence,provider,precision] from a CSV/JSON file."""

    def __init__(self, path: str | Path) -> None:
        self.path = Path(path)
        self._by_site: dict[str, GeocodeResult] = {}
        self._load()

    def _load(self) -> None:
        if not self.path.exists():
            return
        if self.path.suffix.lower() == ".json":
            rows = json.loads(self.path.read_text(encoding="utf-8"))
            if isinstance(rows, dict):
                rows = rows.get("rows") or rows.get("sites") or []
            for row in rows:
                self._ingest(row)
            return
        with self.path.open(encoding="utf-8", newline="") as fh:
            reader = csv.DictReader(fh)
            for row in reader:
                self._ingest(row)

    def _ingest(self, row: dict) -> None:
        site_id = str(row.get("site_id") or "").strip()
        if not site_id:
            return
        try:
            lat = float(row["lat"])
            lng = float(row["lng"])
        except (KeyError, TypeError, ValueError):
            return
        if not is_colombia_latlng(lat, lng):
            return
        confidence = None
        raw_conf = row.get("confidence")
        if raw_conf not in (None, ""):
            try:
                confidence = float(raw_conf)
            except (TypeError, ValueError):
                confidence = None
        min_conf = float(os.getenv("PLACES_GEOCODING_MIN_CONFIDENCE", "0.6"))
        status = "success"
        if confidence is not None and confidence < min_conf:
            status = "low_confidence"
        self._by_site[site_id] = GeocodeResult(
            lat=lat,
            lng=lng,
            confidence=confidence,
            precision=str(row.get("precision") or "address"),
            provider=str(row.get("provider") or "manual_import"),
            status=status,
            query=site_id,
            site_id=site_id,
            error="low_confidence" if status == "low_confidence" else None,
        )

    def geocode(self, query: str, *, site_id: str | None = None) -> GeocodeResult:
        key = site_id or query
        if key in self._by_site:
            return self._by_site[key]
        return GeocodeResult(
            lat=None,
            lng=None,
            confidence=None,
            precision="unknown",
            provider="manual_import",
            status="pending",
            query=query,
            error="site_id not found in manual import file",
            site_id=site_id,
        )


class HttpGeocoder:
    """HTTP geocoder behind env config. Never used unless mode=http and URL is set."""

    def __init__(
        self,
        *,
        transport: Any | None = None,
        attempt_recorder: AttemptRecorder | None = None,
        sleep: Callable[[float], None] | None = None,
        clock: Callable[[], float] | None = None,
        now: Callable[[], str] | None = None,
    ) -> None:
        self.api_url = os.getenv("PLACES_GEOCODING_API_URL", "").strip()
        self.api_key = os.getenv("PLACES_GEOCODING_API_KEY", "").strip()
        self.timeout = float(os.getenv("PLACES_GEOCODING_TIMEOUT_SECONDS", "10"))
        self.retries = int(os.getenv("PLACES_GEOCODING_RETRIES", "1"))
        self.min_confidence = float(os.getenv("PLACES_GEOCODING_MIN_CONFIDENCE", "0.7"))
        self.rate_limit = float(os.getenv("PLACES_GEOCODING_RATE_LIMIT", "0") or "0")
        self._transport = transport
        self._attempt_recorder = attempt_recorder
        self._sleep = sleep or time.sleep
        self._clock = clock or time.monotonic
        self._now = now or _utc_now
        self._last_request_at: float | None = None

    def _throttle(self) -> None:
        if self.rate_limit <= 0:
            return
        min_interval = 1.0 / self.rate_limit
        now = self._clock()
        if self._last_request_at is not None:
            elapsed = now - self._last_request_at
            if elapsed < min_interval:
                self._sleep(min_interval - elapsed)
        self._last_request_at = self._clock()

    def _emit(self, attempt: GeocodeAttemptRecord) -> None:
        if self._attempt_recorder is not None:
            self._attempt_recorder.record(attempt)

    def _make_attempt(
        self,
        *,
        site_id: str | None,
        query: str,
        attempt_number: int,
        status: str,
        attempted_at: str,
        http_status: int | None = None,
        lat: float | None = None,
        lng: float | None = None,
        confidence: float | None = None,
        precision: str | None = None,
        provider_record_id: str | None = None,
        response_payload: Any = None,
        error_code: str | None = None,
        error_message: str | None = None,
    ) -> GeocodeAttemptRecord:
        payload_text = None
        if response_payload is not None:
            payload_text = json.dumps(sanitize_payload(response_payload), ensure_ascii=False)
        record = GeocodeAttemptRecord(
            attempt_id=str(uuid4()),
            site_id=site_id,
            provider="http",
            query=query,
            status=status,
            attempt_number=attempt_number,
            provider_record_id=provider_record_id,
            http_status=http_status,
            lat=lat,
            lng=lng,
            confidence=confidence,
            precision=precision,
            response_payload=payload_text,
            error_code=error_code,
            error_message=error_message,
            attempted_at=attempted_at,
            completed_at=self._now(),
        )
        self._emit(record)
        return record

    def geocode(self, query: str, *, site_id: str | None = None) -> GeocodeResult:
        attempts: list[GeocodeAttemptRecord] = []
        if not self.api_url:
            record = self._make_attempt(
                site_id=site_id,
                query=query,
                attempt_number=1,
                status="failed",
                attempted_at=self._now(),
                error_code="not_configured",
                error_message="PLACES_GEOCODING_API_URL not configured",
            )
            attempts.append(record)
            return GeocodeResult(
                lat=None,
                lng=None,
                confidence=None,
                precision="unknown",
                provider="http",
                status="failed",
                query=query,
                error="PLACES_GEOCODING_API_URL not configured",
                site_id=site_id,
                attempts=attempts,
            )
        try:
            import httpx
        except ImportError:
            record = self._make_attempt(
                site_id=site_id,
                query=query,
                attempt_number=1,
                status="failed",
                attempted_at=self._now(),
                error_code="httpx_missing",
                error_message="httpx not installed",
            )
            attempts.append(record)
            return GeocodeResult(
                lat=None,
                lng=None,
                confidence=None,
                precision="unknown",
                provider="http",
                status="failed",
                query=query,
                error="httpx not installed",
                site_id=site_id,
                attempts=attempts,
            )

        headers = {}
        if self.api_key:
            headers["Authorization"] = f"Bearer {self.api_key}"
        max_attempts = max(1, self.retries)
        last_error: str | None = None
        last_status = "failed"

        for attempt_number in range(1, max_attempts + 1):
            attempted_at = self._now()
            try:
                self._throttle()
                client_kwargs: dict[str, Any] = {"timeout": self.timeout}
                if self._transport is not None:
                    client_kwargs["transport"] = self._transport
                with httpx.Client(**client_kwargs) as client:
                    response = client.get(
                        self.api_url,
                        params={"q": query, "format": "json", "limit": 1},
                        headers=headers,
                    )
                http_status = response.status_code
                if http_status == 429:
                    record = self._make_attempt(
                        site_id=site_id,
                        query=query,
                        attempt_number=attempt_number,
                        status="rate_limited",
                        attempted_at=attempted_at,
                        http_status=http_status,
                        error_code="rate_limited",
                        error_message=response.text[:500] if response.text else "rate_limited",
                    )
                    attempts.append(record)
                    last_status = "rate_limited"
                    last_error = "rate_limited"
                    if attempt_number < max_attempts:
                        self._sleep(0.5 * (2 ** (attempt_number - 1)))
                        continue
                    break
                if 400 <= http_status < 500:
                    record = self._make_attempt(
                        site_id=site_id,
                        query=query,
                        attempt_number=attempt_number,
                        status="provider_4xx",
                        attempted_at=attempted_at,
                        http_status=http_status,
                        error_code="provider_4xx",
                        error_message=response.text[:500] if response.text else f"HTTP {http_status}",
                    )
                    attempts.append(record)
                    return GeocodeResult(
                        lat=None,
                        lng=None,
                        confidence=None,
                        precision="unknown",
                        provider="http",
                        status="provider_4xx",
                        query=query,
                        error=f"HTTP {http_status}",
                        site_id=site_id,
                        attempts=attempts,
                    )
                if http_status >= 500:
                    record = self._make_attempt(
                        site_id=site_id,
                        query=query,
                        attempt_number=attempt_number,
                        status="provider_5xx",
                        attempted_at=attempted_at,
                        http_status=http_status,
                        error_code="provider_5xx",
                        error_message=response.text[:500] if response.text else f"HTTP {http_status}",
                    )
                    attempts.append(record)
                    last_status = "provider_5xx"
                    last_error = f"HTTP {http_status}"
                    if attempt_number < max_attempts:
                        self._sleep(0.5 * (2 ** (attempt_number - 1)))
                        continue
                    break

                try:
                    data = response.json()
                except Exception as exc:  # noqa: BLE001
                    record = self._make_attempt(
                        site_id=site_id,
                        query=query,
                        attempt_number=attempt_number,
                        status="invalid_json",
                        attempted_at=attempted_at,
                        http_status=http_status,
                        error_code="invalid_json",
                        error_message=str(exc),
                        response_payload={"raw": (response.text or "")[:500]},
                    )
                    attempts.append(record)
                    return GeocodeResult(
                        lat=None,
                        lng=None,
                        confidence=None,
                        precision="unknown",
                        provider="http",
                        status="invalid_json",
                        query=query,
                        error=str(exc),
                        site_id=site_id,
                        attempts=attempts,
                    )

                if isinstance(data, list):
                    item = data[0] if data else None
                elif isinstance(data, dict):
                    item = (data.get("results") or [None])[0]
                else:
                    item = None
                if not item:
                    record = self._make_attempt(
                        site_id=site_id,
                        query=query,
                        attempt_number=attempt_number,
                        status="empty_result",
                        attempted_at=attempted_at,
                        http_status=http_status,
                        response_payload=data,
                        error_code="empty_result",
                        error_message="empty_result",
                    )
                    attempts.append(record)
                    return GeocodeResult(
                        lat=None,
                        lng=None,
                        confidence=None,
                        precision="unknown",
                        provider="http",
                        status="empty_result",
                        query=query,
                        error="empty_result",
                        site_id=site_id,
                        attempts=attempts,
                    )

                lat = float(item.get("lat") or item.get("latitude"))
                lng = float(item.get("lon") or item.get("lng") or item.get("longitude"))
                provider_record_id = str(item.get("place_id") or item.get("id") or "") or None
                precision = str(item.get("precision") or "address")
                confidence = float(item.get("importance") or item.get("confidence") or 0.0)

                if not is_colombia_latlng(lat, lng):
                    record = self._make_attempt(
                        site_id=site_id,
                        query=query,
                        attempt_number=attempt_number,
                        status="outside_colombia",
                        attempted_at=attempted_at,
                        http_status=http_status,
                        lat=lat,
                        lng=lng,
                        confidence=confidence or None,
                        precision=precision,
                        provider_record_id=provider_record_id,
                        response_payload=sanitize_payload(item),
                        error_code="outside_colombia",
                        error_message="coordinates_outside_colombia",
                    )
                    attempts.append(record)
                    return GeocodeResult(
                        lat=None,
                        lng=None,
                        confidence=None,
                        precision="unknown",
                        provider="http",
                        status="outside_colombia",
                        query=query,
                        error="coordinates_outside_colombia",
                        site_id=site_id,
                        attempts=attempts,
                    )

                if confidence and confidence < self.min_confidence:
                    record = self._make_attempt(
                        site_id=site_id,
                        query=query,
                        attempt_number=attempt_number,
                        status="low_confidence",
                        attempted_at=attempted_at,
                        http_status=http_status,
                        lat=lat,
                        lng=lng,
                        confidence=confidence,
                        precision=precision,
                        provider_record_id=provider_record_id,
                        response_payload=sanitize_payload(item),
                        error_code="low_confidence",
                        error_message="low_confidence",
                    )
                    attempts.append(record)
                    return GeocodeResult(
                        lat=lat,
                        lng=lng,
                        confidence=confidence,
                        precision=precision,
                        provider="http",
                        status="low_confidence",
                        query=query,
                        error="low_confidence",
                        site_id=site_id,
                        attempts=attempts,
                    )

                record = self._make_attempt(
                    site_id=site_id,
                    query=query,
                    attempt_number=attempt_number,
                    status="success",
                    attempted_at=attempted_at,
                    http_status=http_status,
                    lat=lat,
                    lng=lng,
                    confidence=confidence or None,
                    precision=precision,
                    provider_record_id=provider_record_id,
                    response_payload=sanitize_payload(item),
                )
                attempts.append(record)
                return GeocodeResult(
                    lat=lat,
                    lng=lng,
                    confidence=confidence or None,
                    precision=precision,
                    provider="http",
                    status="success",
                    query=query,
                    site_id=site_id,
                    attempts=attempts,
                )
            except Exception as exc:  # noqa: BLE001
                import httpx as _httpx

                is_timeout = isinstance(
                    exc,
                    (
                        _httpx.TimeoutException,
                        TimeoutError,
                    ),
                )
                status = "timeout" if is_timeout else "transport_error"
                record = self._make_attempt(
                    site_id=site_id,
                    query=query,
                    attempt_number=attempt_number,
                    status=status,
                    attempted_at=attempted_at,
                    error_code=status,
                    error_message=str(exc),
                )
                attempts.append(record)
                last_status = status
                last_error = str(exc)
                if attempt_number < max_attempts:
                    self._sleep(0.5 * (2 ** (attempt_number - 1)))
                    continue
                break

        return GeocodeResult(
            lat=None,
            lng=None,
            confidence=None,
            precision="unknown",
            provider="http",
            status=last_status,
            query=query,
            error=last_error or "http_geocode_failed",
            site_id=site_id,
            attempts=attempts,
        )


def persist_geocode_attempts(conn, attempts: list[GeocodeAttemptRecord], *, import_run_id: str | None = None) -> None:
    """Persist attempt records into places_geocode_attempts (caller owns transaction)."""
    from places_service.adapters.outbound.schema import places_geocode_attempts

    for attempt in attempts:
        payload = asdict(attempt)
        payload["import_run_id"] = import_run_id
        # site_id is NOT NULL in schema; use empty sentinel when unknown
        if not payload.get("site_id"):
            payload["site_id"] = "unknown"
        conn.execute(places_geocode_attempts.insert().values(**payload))


def geocoder_from_env(
    *,
    transport: Any | None = None,
    attempt_recorder: AttemptRecorder | None = None,
) -> Geocoder:
    mode = os.getenv("PLACES_GEOCODING_MODE", "disabled").strip().lower()
    if mode in {"", "disabled", "off", "none"}:
        return DisabledGeocoder()
    if mode == "manual_import":
        path = os.getenv("PLACES_GEOCODING_MANUAL_PATH", "").strip()
        if not path:
            return DisabledGeocoder()
        return ManualImportGeocoder(path)
    if mode == "http":
        if not os.getenv("PLACES_GEOCODING_API_URL", "").strip():
            return DisabledGeocoder()
        return HttpGeocoder(transport=transport, attempt_recorder=attempt_recorder)
    return DisabledGeocoder()
