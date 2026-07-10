"""OSRM table client: driving distance/duration for nearest re-rank.

Hybrid strategy: Haversine prefilters candidates; OSRM `/table/v1/driving`
reorders by road km when `OSRM_BASE_URL` is set. On any failure, callers keep
Haversine distances.
"""

from __future__ import annotations

import logging
import os
from typing import Final

import httpx

logger = logging.getLogger(__name__)

_ROUTE_CACHE: dict[
    tuple[tuple[float, float], tuple[float, float]],
    tuple[float, float] | None,
] = {}
_CACHE_MAX_SIZE: Final[int] = 4096


def _round_coord(point: tuple[float, float]) -> tuple[float, float]:
    return (round(point[0], 5), round(point[1], 5))


def _trim_cache_if_needed() -> None:
    if len(_ROUTE_CACHE) <= _CACHE_MAX_SIZE:
        return
    for key in list(_ROUTE_CACHE)[:256]:
        _ROUTE_CACHE.pop(key, None)


def clear_cache() -> None:
    _ROUTE_CACHE.clear()


def is_enabled() -> bool:
    return bool(os.getenv("OSRM_BASE_URL", "").strip())


def max_destinations() -> int:
    raw = os.getenv("OSRM_MAX_DESTINATIONS", "16").strip()
    try:
        return max(1, int(raw))
    except ValueError:
        return 16


def timeout_seconds() -> float:
    raw = os.getenv("OSRM_TIMEOUT_S", "4").strip()
    try:
        return max(0.5, float(raw))
    except ValueError:
        return 4.0


def table(
    origin: tuple[float, float],
    destinations: list[tuple[float, float]],
) -> list[tuple[float, float] | None] | None:
    """Return per-destination (km, minutes) or None on disable/failure.

    Each list item is `(km, minutes)` or `None` if OSRM has no route for that
    destination. Outer `None` means fall back to Haversine entirely.
    """
    base = os.getenv("OSRM_BASE_URL", "").strip().rstrip("/")
    if not base:
        return None
    if not destinations:
        return []

    max_n = max_destinations()
    if len(destinations) > max_n:
        destinations = destinations[:max_n]

    rounded_origin = _round_coord(origin)
    rounded_dests = [_round_coord(d) for d in destinations]

    cached_results: list[tuple[float, float] | None] = []
    missing_idx: list[int] = []
    for i, dest in enumerate(rounded_dests):
        key = (rounded_origin, dest)
        if key in _ROUTE_CACHE:
            cached_results.append(_ROUTE_CACHE[key])
        else:
            cached_results.append(None)
            missing_idx.append(i)

    if not missing_idx:
        return cached_results

    coords_parts = [f"{rounded_origin[1]:.5f},{rounded_origin[0]:.5f}"]
    coords_parts.extend(
        f"{rounded_dests[i][1]:.5f},{rounded_dests[i][0]:.5f}" for i in missing_idx
    )
    url = f"{base}/table/v1/driving/{';'.join(coords_parts)}"
    params = {"sources": "0", "annotations": "duration,distance"}

    try:
        with httpx.Client(timeout=timeout_seconds()) as client:
            resp = client.get(url, params=params)
            resp.raise_for_status()
            data = resp.json()
    except (httpx.HTTPError, ValueError) as exc:
        logger.warning("osrm.table failed (%s): %s", type(exc).__name__, exc)
        return None

    if data.get("code") != "Ok":
        logger.warning("osrm.table code=%s", data.get("code"))
        return None

    try:
        dist_matrix = data["distances"][0][1:]
        dur_matrix = data["durations"][0][1:]
    except (KeyError, IndexError, TypeError) as exc:
        logger.warning("osrm.table missing matrices: %s", exc)
        return None

    if len(dist_matrix) != len(missing_idx) or len(dur_matrix) != len(missing_idx):
        logger.warning(
            "osrm.table mismatch dist=%d dur=%d expected=%d",
            len(dist_matrix),
            len(dur_matrix),
            len(missing_idx),
        )
        return None

    for slot, dist_m, dur_s in zip(missing_idx, dist_matrix, dur_matrix):
        key = (rounded_origin, rounded_dests[slot])
        if dist_m is None or dur_s is None:
            _ROUTE_CACHE[key] = None
            cached_results[slot] = None
            continue
        try:
            value = (float(dist_m) / 1000.0, float(dur_s) / 60.0)
        except (TypeError, ValueError):
            _ROUTE_CACHE[key] = None
            cached_results[slot] = None
            continue
        _ROUTE_CACHE[key] = value
        cached_results[slot] = value

    _trim_cache_if_needed()
    return cached_results
