from __future__ import annotations

"""Geographic bounding boxes and centroids.

Manizales and Santander municipal envelopes are active for their respective
validated-geocode import scopes. Do not widen Girón to absorb out-of-municipality
coordinates — that would hide CSV city assignment errors.
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


# Active: Manizales (Caldas).
MANIZALES_BBOX = BBox(lat_min=4.95, lat_max=5.15, lng_min=-75.60, lng_max=-75.40)
MANIZALES_CENTROID: tuple[float, float] = (5.0689, -75.5174)

# Active: Santander prioritized municipalities (per-city envelopes).
BUCARAMANGA_BBOX = BBox(lat_min=7.08, lat_max=7.16, lng_min=-73.17, lng_max=-73.10)
FLORIDABLANCA_BBOX = BBox(lat_min=7.05, lat_max=7.12, lng_min=-73.12, lng_max=-73.08)
GIRON_BBOX = BBox(lat_min=7.055, lat_max=7.09, lng_min=-73.18, lng_max=-73.15)
PIEDECUESTA_BBOX = BBox(lat_min=6.97, lat_max=7.04, lng_min=-73.08, lng_max=-73.04)

# Convenience envelope spanning the four municipalities (maps / diagnostics only).
# NEVER use this for per-row import validation.
BUCARAMANGA_METRO_BBOX = BBox(lat_min=6.90, lat_max=7.25, lng_min=-73.25, lng_max=-73.00)
BUCARAMANGA_CENTROID: tuple[float, float] = (7.1193, -73.1227)


def in_manizales_bbox(lat: float, lng: float) -> bool:
    """True when the coordinate falls inside the Manizales envelope."""
    return MANIZALES_BBOX.contains(lat, lng)


def in_giron_bbox(lat: float, lng: float) -> bool:
    """True when the coordinate falls inside the Girón municipal envelope."""
    return GIRON_BBOX.contains(lat, lng)


__all__ = [
    "BBox",
    "MANIZALES_BBOX",
    "MANIZALES_CENTROID",
    "BUCARAMANGA_BBOX",
    "FLORIDABLANCA_BBOX",
    "GIRON_BBOX",
    "PIEDECUESTA_BBOX",
    "BUCARAMANGA_METRO_BBOX",
    "BUCARAMANGA_CENTROID",
    "in_manizales_bbox",
    "in_giron_bbox",
]
