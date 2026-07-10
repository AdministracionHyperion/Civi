"""Minimal geometry tests for Manizales nomenclatura audit (no network, no CSV)."""
from __future__ import annotations

import math
import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(Path(__file__).resolve().parent))

from manizales_nomenclatura_geometry import (  # noqa: E402
    classify_esri_rings,
    deterministic_point_on_surface,
    interpolate_representative_points,
    point_in_polygon,
    polygon_area_centroid,
    representative_point,
)


def _square(origin_lng: float = 0.0, origin_lat: float = 0.0, size: float = 2.0) -> dict:
    x0, y0, s = origin_lng, origin_lat, size
    return {
        "rings": [
            [
                [x0, y0],
                [x0 + s, y0],
                [x0 + s, y0 + s],
                [x0, y0 + s],
                [x0, y0],
            ]
        ]
    }


def _triangle() -> dict:
    return {
        "rings": [
            [
                [0.0, 0.0],
                [4.0, 0.0],
                [0.0, 6.0],
                [0.0, 0.0],
            ]
        ]
    }


def _concave_c() -> dict:
    # C-shaped polygon; area centroid falls outside the solid region.
    return {
        "rings": [
            [
                [0.0, 0.0],
                [4.0, 0.0],
                [4.0, 1.0],
                [1.0, 1.0],
                [1.0, 3.0],
                [4.0, 3.0],
                [4.0, 4.0],
                [0.0, 4.0],
                [0.0, 0.0],
            ]
        ]
    }


def test_square_area_centroid():
    geom = _square()
    lat, lng = polygon_area_centroid(geom)
    assert abs(lat - 1.0) < 1e-9
    assert abs(lng - 1.0) < 1e-9
    assert point_in_polygon(lat, lng, geom)
    rep = representative_point(geom)
    assert rep["derivation_method"] == "polygon_area_centroid"
    assert rep["inside_polygon"] is True


def test_triangle_area_centroid():
    geom = _triangle()
    lat, lng = polygon_area_centroid(geom)
    # Centroid of right triangle with vertices (0,0),(4,0),(0,6) is (4/3, 2)
    assert abs(lng - 4.0 / 3.0) < 1e-9
    assert abs(lat - 2.0) < 1e-9
    assert point_in_polygon(lat, lng, geom)


def test_translated_near_manizales_stable():
    size = 0.002
    origin_lng, origin_lat = -75.52, 5.06
    shifted = _square(origin_lng=origin_lng, origin_lat=origin_lat, size=size)
    lat1, lng1 = polygon_area_centroid(shifted)
    # Relative centroid of axis-aligned square is at size/2 from origin.
    assert abs(lat1 - (origin_lat + size / 2)) < 1e-12
    assert abs(lng1 - (origin_lng + size / 2)) < 1e-12
    assert point_in_polygon(lat1, lng1, shifted)
    # Same shape at (0,0) then translated must match absolute centroid.
    base = _square(origin_lng=0.0, origin_lat=0.0, size=size)
    lat0, lng0 = polygon_area_centroid(base)
    assert abs((lat0 + origin_lat) - lat1) < 1e-12
    assert abs((lng0 + origin_lng) - lng1) < 1e-12


def test_concave_uses_point_on_surface_when_centroid_outside():
    geom = _concave_c()
    clat, clng = polygon_area_centroid(geom)
    assert not point_in_polygon(clat, clng, geom)
    rep = representative_point(geom)
    assert rep["derivation_method"] == "point_on_surface"
    assert rep["inside_polygon"] is True
    assert point_in_polygon(rep["lat"], rep["lng"], geom)
    pos = deterministic_point_on_surface(geom)
    assert pos is not None
    assert point_in_polygon(pos[0], pos[1], geom)


def test_interpolation_38_44_toward_40():
    before = {"representative_lat": 5.0680505, "representative_lng": -75.5218138, "objectid": 80394}
    after = {"representative_lat": 5.0680436, "representative_lng": -75.5217448, "objectid": 80393}
    inter = interpolate_representative_points(
        before,
        after,
        target_plate=40,
        before_plate=38,
        after_plate=44,
        formula="(40-38)/(44-38)=1/3",
    )
    assert inter["t"] == pytest.approx(1.0 / 3.0, rel=1e-6)
    assert 0.0 <= inter["t"] <= 1.0
    assert inter["lat"] == pytest.approx(
        before["representative_lat"] + (1 / 3) * (after["representative_lat"] - before["representative_lat"]),
        abs=1e-7,
    )
    assert "centroid" not in inter["method"]


def test_interpolation_55_75_toward_59():
    before = {"representative_lat": 5.0518715, "representative_lng": -75.4841155, "objectid": 105038}
    after = {"representative_lat": 5.0517179, "representative_lng": -75.4840623, "objectid": 105040}
    inter = interpolate_representative_points(
        before,
        after,
        target_plate=59,
        before_plate=55,
        after_plate=75,
        formula="(59-55)/(75-55)=0.20",
    )
    assert inter["t"] == pytest.approx(0.20, abs=1e-9)
    assert 0.0 <= inter["t"] <= 1.0
    expected_lat = before["representative_lat"] + 0.2 * (
        after["representative_lat"] - before["representative_lat"]
    )
    expected_lng = before["representative_lng"] + 0.2 * (
        after["representative_lng"] - before["representative_lng"]
    )
    assert inter["lat"] == pytest.approx(expected_lat, abs=1e-7)
    assert inter["lng"] == pytest.approx(expected_lng, abs=1e-7)


def test_clockwise_ring_same_centroid():
    ccw = _square()
    cw = {
        "rings": [
            list(reversed(ccw["rings"][0]))
        ]
    }
    lat1, lng1 = polygon_area_centroid(ccw)
    lat2, lng2 = polygon_area_centroid(cw)
    assert abs(lat1 - lat2) < 1e-9
    assert abs(lng1 - lng2) < 1e-9


def _square_ring(x0: float, y0: float, size: float, closed: bool = True) -> list[list[float]]:
    ring = [
        [x0, y0],
        [x0 + size, y0],
        [x0 + size, y0 + size],
        [x0, y0 + size],
    ]
    if closed:
        ring.append([x0, y0])
    return ring


def test_polygon_with_hole():
    # Outer 0..4, hole 1..3 — point in hole is outside filled region.
    geom = {
        "rings": [
            _square_ring(0.0, 0.0, 4.0),
            list(reversed(_square_ring(1.0, 1.0, 2.0))),  # opposite orientation hole
        ]
    }
    assert point_in_polygon(0.5, 0.5, geom) is True
    assert point_in_polygon(2.0, 2.0, geom) is False  # inside hole
    assert point_in_polygon(3.5, 3.5, geom) is True
    # Hole listed first should still work (no rings[0]-only assumption).
    geom_swapped = {"rings": [geom["rings"][1], geom["rings"][0]]}
    assert point_in_polygon(0.5, 0.5, geom_swapped) is True
    assert point_in_polygon(2.0, 2.0, geom_swapped) is False


def test_two_separate_exteriors_and_point_in_second():
    geom = {
        "rings": [
            _square_ring(0.0, 0.0, 1.0),
            _square_ring(5.0, 5.0, 1.0),
        ]
    }
    assert point_in_polygon(0.5, 0.5, geom) is True
    assert point_in_polygon(2.0, 2.0, geom) is False
    assert point_in_polygon(5.5, 5.5, geom) is True  # second exterior
    parts = classify_esri_rings(geom)
    assert len(parts) == 2
    assert all(len(p["holes"]) == 0 for p in parts)


def test_degenerate_polygon():
    geom = {"rings": [[[0.0, 0.0], [1.0, 1.0], [0.0, 0.0]]]}  # zero area
    assert point_in_polygon(0.5, 0.5, geom) is False
    assert polygon_area_centroid(geom) is None
    rep = representative_point(geom)
    assert rep["needs_review"] is True
    assert rep["lat"] is not None


if __name__ == "__main__":
    raise SystemExit(pytest.main([__file__, "-q"]))
