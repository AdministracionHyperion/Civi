from __future__ import annotations

"""Geographic bounding boxes and centroids.

Only Manizales is active. Bucaramanga metro constants are declared for a future
Santander rollout and must NOT be referenced by the Manizales import path.
"""

from dataclasses import dataclass


@dataclass(frozen=True)
class BBox:
    lat_min: float
    lat_max: float
    lng_min: float
    lng_max: float

    def contains(self, lat: float, lng: float) -> bool:
        return (
            self.lat_min <= lat <= self.lat_max
            and self.lng_min <= lng <= self.lng_max
        )


# Active: Manizales (Caldas). Requested envelope for the validated geocode file.
MANIZALES_BBOX = BBox(lat_min=4.95, lat_max=5.15, lng_min=-75.60, lng_max=-75.40)

# Approximate municipal centroid (Plaza de Bolívar / Alcaldía de Manizales).
# Used to reject centroid-like fixes from being presented as a confirmed business.
MANIZALES_CENTROID: tuple[float, float] = (5.0689, -75.5174)

# --- Stubs for a future Santander / Bucaramanga metropolitan rollout. ---
# Declared intentionally and NOT used by the Manizales import. Do not wire these
# into validation without a dedicated, reviewed change.
BUCARAMANGA_METRO_BBOX = BBox(lat_min=6.90, lat_max=7.25, lng_min=-73.25, lng_max=-73.00)
BUCARAMANGA_CENTROID: tuple[float, float] = (7.1193, -73.1227)


def in_manizales_bbox(lat: float, lng: float) -> bool:
    """True when the coordinate falls inside the Manizales envelope."""
    return MANIZALES_BBOX.contains(lat, lng)


__all__ = [
    "BBox",
    "MANIZALES_BBOX",
    "MANIZALES_CENTROID",
    "BUCARAMANGA_METRO_BBOX",
    "BUCARAMANGA_CENTROID",
    "in_manizales_bbox",
]
