from __future__ import annotations

LAT_MIN, LAT_MAX = -4.3, 13.0
LNG_MIN, LNG_MAX = -79.0, -66.8


def is_colombia_latlng(lat: float, lng: float) -> bool:
    return LAT_MIN <= lat <= LAT_MAX and LNG_MIN <= lng <= LNG_MAX
