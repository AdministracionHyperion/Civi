from __future__ import annotations

"""Geocoding adapters — disabled by default; no external calls in tests."""

import csv
import json
import os
from dataclasses import dataclass
from pathlib import Path
from typing import Protocol

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


class Geocoder(Protocol):
    def geocode(self, query: str, *, site_id: str | None = None) -> GeocodeResult:
        ...


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
            status = "manual"
        self._by_site[site_id] = GeocodeResult(
            lat=lat,
            lng=lng,
            confidence=confidence,
            precision=str(row.get("precision") or "address"),
            provider=str(row.get("provider") or "manual_import"),
            status=status,
            query=site_id,
            site_id=site_id,
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

    def __init__(self) -> None:
        self.api_url = os.getenv("PLACES_GEOCODING_API_URL", "").strip()
        self.api_key = os.getenv("PLACES_GEOCODING_API_KEY", "").strip()
        self.timeout = float(os.getenv("PLACES_GEOCODING_TIMEOUT_SECONDS", "10"))
        self.retries = int(os.getenv("PLACES_GEOCODING_RETRIES", "1"))
        self.min_confidence = float(os.getenv("PLACES_GEOCODING_MIN_CONFIDENCE", "0.7"))

    def geocode(self, query: str, *, site_id: str | None = None) -> GeocodeResult:
        if not self.api_url:
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
            )
        # Intentionally conservative: require httpx and never invent coordinates.
        try:
            import httpx
        except ImportError:
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
            )

        headers = {}
        if self.api_key:
            headers["Authorization"] = f"Bearer {self.api_key}"
        last_error = None
        for _ in range(max(1, self.retries)):
            try:
                with httpx.Client(timeout=self.timeout) as client:
                    response = client.get(
                        self.api_url,
                        params={"q": query, "format": "json", "limit": 1},
                        headers=headers,
                    )
                    response.raise_for_status()
                    data = response.json()
                item = data[0] if isinstance(data, list) and data else (data.get("results") or [None])[0]
                if not item:
                    return GeocodeResult(
                        lat=None,
                        lng=None,
                        confidence=None,
                        precision="unknown",
                        provider="http",
                        status="failed",
                        query=query,
                        error="empty_result",
                        site_id=site_id,
                    )
                lat = float(item.get("lat") or item.get("latitude"))
                lng = float(item.get("lon") or item.get("lng") or item.get("longitude"))
                if not is_colombia_latlng(lat, lng):
                    return GeocodeResult(
                        lat=None,
                        lng=None,
                        confidence=None,
                        precision="unknown",
                        provider="http",
                        status="failed",
                        query=query,
                        error="coordinates_outside_colombia",
                        site_id=site_id,
                    )
                confidence = float(item.get("importance") or item.get("confidence") or 0.0)
                if confidence and confidence < self.min_confidence:
                    return GeocodeResult(
                        lat=lat,
                        lng=lng,
                        confidence=confidence,
                        precision="unknown",
                        provider="http",
                        status="manual",
                        query=query,
                        error="low_confidence",
                        site_id=site_id,
                    )
                return GeocodeResult(
                    lat=lat,
                    lng=lng,
                    confidence=confidence or None,
                    precision=str(item.get("precision") or "address"),
                    provider="http",
                    status="success",
                    query=query,
                    site_id=site_id,
                )
            except Exception as exc:  # noqa: BLE001
                last_error = str(exc)
        return GeocodeResult(
            lat=None,
            lng=None,
            confidence=None,
            precision="unknown",
            provider="http",
            status="failed",
            query=query,
            error=last_error or "http_geocode_failed",
            site_id=site_id,
        )


def geocoder_from_env() -> Geocoder:
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
        return HttpGeocoder()
    return DisabledGeocoder()
