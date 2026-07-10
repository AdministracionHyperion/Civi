from __future__ import annotations

"""Match scoring helpers for geocode validation.

Scores are intentionally *separate* per signal (name / address / phone /
municipality) so callers can reason about each independently instead of a single
opaque number. Nothing here mutates state or performs I/O.

Centroid guard: a fix that lands on the municipal centroid is never accepted as a
confirmed *business* — municipal centroids are the classic false-positive for an
un-geocodable address, so ``accepts_centroid_as_business`` always returns False.
"""

import math
import re
import unicodedata
from difflib import SequenceMatcher

from .bounds import MANIZALES_CENTROID
from .colombia_address import normalize_colombia_address


def _norm(value: str | None) -> str:
    text = "".join(
        ch for ch in unicodedata.normalize("NFKD", value or "") if not unicodedata.combining(ch)
    )
    return re.sub(r"\s+", " ", text.upper()).strip()


def _digits(value: str | None) -> str:
    return re.sub(r"\D", "", value or "")


def score_name(a: str | None, b: str | None) -> float:
    """Fuzzy similarity of two business names in [0, 1]."""
    na, nb = _norm(a), _norm(b)
    if not na or not nb:
        return 0.0
    if na == nb:
        return 1.0
    return round(SequenceMatcher(None, na, nb).ratio(), 4)


def score_address(a: str | None, b: str | None) -> float:
    """Similarity of two addresses after Colombian vía normalization."""
    na, nb = normalize_colombia_address(a), normalize_colombia_address(b)
    if not na or not nb:
        return 0.0
    if na == nb:
        return 1.0
    return round(SequenceMatcher(None, na, nb).ratio(), 4)


def score_phone(a: str | None, b: str | None) -> float:
    """1.0 when the significant tail of both phone numbers matches, else 0.0."""
    da, db = _digits(a), _digits(b)
    if len(da) < 7 or len(db) < 7:
        return 0.0
    return 1.0 if da[-7:] == db[-7:] else 0.0


def score_municipality(a: str | None, b: str | None) -> float:
    """1.0 when municipalities match after normalization, else 0.0."""
    na, nb = _norm(a), _norm(b)
    if not na or not nb:
        return 0.0
    return 1.0 if na == nb else 0.0


def _haversine_m(lat1: float, lng1: float, lat2: float, lng2: float) -> float:
    radius = 6_371_000.0
    dlat = math.radians(lat2 - lat1)
    dlng = math.radians(lng2 - lng1)
    a = (
        math.sin(dlat / 2) ** 2
        + math.cos(math.radians(lat1)) * math.cos(math.radians(lat2)) * math.sin(dlng / 2) ** 2
    )
    return radius * 2 * math.atan2(math.sqrt(a), math.sqrt(1 - a))


def is_municipal_centroid(
    lat: float,
    lng: float,
    *,
    centroid: tuple[float, float] = MANIZALES_CENTROID,
    tolerance_m: float = 60.0,
) -> bool:
    """True when (lat, lng) sits on the municipal centroid within tolerance."""
    return _haversine_m(lat, lng, centroid[0], centroid[1]) <= tolerance_m


def accepts_centroid_as_business(*_args: object, **_kwargs: object) -> bool:
    """Policy: a municipal centroid is NEVER a confirmed business location."""
    return False


__all__ = [
    "score_name",
    "score_address",
    "score_phone",
    "score_municipality",
    "is_municipal_centroid",
    "accepts_centroid_as_business",
]
