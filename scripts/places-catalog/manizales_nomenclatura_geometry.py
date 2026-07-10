"""Polygon representative-point helpers for Manizales NOMENCLATURA PREDIAL audit.

Coordinates are (x=lng, y=lat). Area centroid uses the shoelace formula with
temporary translation to the first vertex for numerical stability.
"""
from __future__ import annotations

import math
from typing import Any

AREA_EPS = 1e-18
COORD_EPS = 1e-12


def _normalize_ring(ring: list[list[float]] | list[tuple[float, float]]) -> list[tuple[float, float]]:
    pts = [(float(p[0]), float(p[1])) for p in ring]
    if len(pts) >= 2 and abs(pts[0][0] - pts[-1][0]) <= COORD_EPS and abs(pts[0][1] - pts[-1][1]) <= COORD_EPS:
        pts = pts[:-1]
    return pts


def _ring_signed_area_and_centroid(
    ring: list[tuple[float, float]],
) -> tuple[float, float, float] | None:
    """Return (signed_area, cx, cy) in absolute coordinates, or None if degenerate."""
    pts = _normalize_ring(ring)
    if len(pts) < 3:
        return None
    x0, y0 = pts[0]
    # Translate so first vertex is origin (stable with geographic coords).
    local = [(x - x0, y - y0) for x, y in pts]
    area2 = 0.0
    cx6 = 0.0
    cy6 = 0.0
    n = len(local)
    for i in range(n):
        x1, y1 = local[i]
        x2, y2 = local[(i + 1) % n]
        cross = x1 * y2 - x2 * y1
        area2 += cross
        cx6 += (x1 + x2) * cross
        cy6 += (y1 + y2) * cross
    if abs(area2) < AREA_EPS:
        return None
    signed_area = area2 / 2.0
    cx_local = cx6 / (3.0 * area2)
    cy_local = cy6 / (3.0 * area2)
    return signed_area, x0 + cx_local, y0 + cy_local


def polygon_area_centroid(geom: dict[str, Any]) -> tuple[float, float] | None:
    """Area-weighted centroid of an Esri polygon (lat, lng). Handles multi-ring."""
    rings = geom.get("rings") or []
    if not rings:
        return None
    total_area = 0.0
    cx_acc = 0.0
    cy_acc = 0.0
    for ring in rings:
        part = _ring_signed_area_and_centroid(ring)
        if part is None:
            continue
        signed_area, cx, cy = part
        total_area += signed_area
        cx_acc += cx * signed_area
        cy_acc += cy * signed_area
    if abs(total_area) < AREA_EPS:
        return None
    # Return (lat, lng) = (y, x)
    return cy_acc / total_area, cx_acc / total_area


def _point_in_ring(x: float, y: float, ring: list[tuple[float, float]]) -> bool:
    """Ray casting; boundary counts as inside."""
    pts = _normalize_ring(ring)
    if len(pts) < 3:
        return False
    inside = False
    n = len(pts)
    for i in range(n):
        x1, y1 = pts[i]
        x2, y2 = pts[(i + 1) % n]
        # On vertex
        if abs(x - x1) <= COORD_EPS and abs(y - y1) <= COORD_EPS:
            return True
        # On horizontal edge
        if abs(y1 - y2) <= COORD_EPS:
            if abs(y - y1) <= COORD_EPS and min(x1, x2) - COORD_EPS <= x <= max(x1, x2) + COORD_EPS:
                return True
            continue
        # Crossings
        if (y1 > y) != (y2 > y):
            x_int = x1 + (y - y1) * (x2 - x1) / (y2 - y1)
            if abs(x_int - x) <= COORD_EPS:
                return True
            if x_int > x:
                inside = not inside
    return inside


def point_in_polygon(lat: float, lng: float, geom: dict[str, Any]) -> bool:
    """True if (lat,lng) is inside exterior and outside holes."""
    rings = geom.get("rings") or []
    if not rings:
        return False
    x, y = lng, lat
    exterior = _normalize_ring(rings[0])
    if not _point_in_ring(x, y, exterior):
        return False
    for hole in rings[1:]:
        if _point_in_ring(x, y, hole):
            return False
    return True


def _bbox(ring: list[tuple[float, float]]) -> tuple[float, float, float, float]:
    xs = [p[0] for p in ring]
    ys = [p[1] for p in ring]
    return min(xs), min(ys), max(xs), max(ys)


def _horizontal_intersections(y: float, ring: list[tuple[float, float]]) -> list[float]:
    pts = _normalize_ring(ring)
    xs: list[float] = []
    n = len(pts)
    for i in range(n):
        x1, y1 = pts[i]
        x2, y2 = pts[(i + 1) % n]
        if abs(y1 - y2) <= COORD_EPS:
            continue
        if (y1 > y) != (y2 > y) or abs(y1 - y) <= COORD_EPS:
            # Standard segment intersection with horizontal line; skip upper endpoint to avoid double count
            if max(y1, y2) - COORD_EPS < y:
                continue
            if min(y1, y2) > y + COORD_EPS:
                continue
            if abs(y2 - y1) <= COORD_EPS:
                continue
            t = (y - y1) / (y2 - y1)
            if t < -COORD_EPS or t > 1 + COORD_EPS:
                continue
            xs.append(x1 + t * (x2 - x1))
    xs.sort()
    return xs


def deterministic_point_on_surface(geom: dict[str, Any], scan_lines: int = 21) -> tuple[float, float] | None:
    """Deterministic interior point: midpoint of the longest interior scan segment."""
    rings = geom.get("rings") or []
    if not rings:
        return None
    exterior = _normalize_ring(rings[0])
    if len(exterior) < 3:
        return None
    xmin, ymin, xmax, ymax = _bbox(exterior)
    if abs(ymax - ymin) < COORD_EPS or abs(xmax - xmin) < COORD_EPS:
        # Degenerate thin polygon: use first vertex.
        return exterior[0][1], exterior[0][0]
    best: tuple[float, float, float] | None = None  # (length, x, y)
    for i in range(scan_lines):
        y = ymin + (i + 0.5) * (ymax - ymin) / scan_lines
        xs = _horizontal_intersections(y, exterior)
        # Pair consecutive intersections as interior segments (even-odd).
        for j in range(0, len(xs) - 1, 2):
            x_left, x_right = xs[j], xs[j + 1]
            if x_right <= x_left:
                continue
            mid_x = (x_left + x_right) / 2.0
            mid_y = y
            if not point_in_polygon(mid_y, mid_x, geom):
                continue
            length = x_right - x_left
            if best is None or length > best[0] + COORD_EPS or (
                abs(length - best[0]) <= COORD_EPS and (mid_y, mid_x) < (best[2], best[1])
            ):
                best = (length, mid_x, mid_y)
    if best is None:
        return None
    return best[2], best[1]  # lat, lng


def representative_point(geom: dict[str, Any]) -> dict[str, Any]:
    """Choose polygon_area_centroid if inside; else deterministic point_on_surface."""
    rings = geom.get("rings") or []
    if not rings:
        return {
            "lat": None,
            "lng": None,
            "derivation_method": None,
            "inside_polygon": False,
            "needs_review": True,
            "reason": "empty_geometry",
        }

    centroid = polygon_area_centroid(geom)
    if centroid is not None:
        lat, lng = centroid
        if point_in_polygon(lat, lng, geom):
            return {
                "lat": lat,
                "lng": lng,
                "derivation_method": "polygon_area_centroid",
                "inside_polygon": True,
                "needs_review": False,
                "reason": None,
            }
        pos = deterministic_point_on_surface(geom)
        if pos is not None:
            plat, plng = pos
            return {
                "lat": plat,
                "lng": plng,
                "derivation_method": "point_on_surface",
                "inside_polygon": point_in_polygon(plat, plng, geom),
                "needs_review": False,
                "area_centroid_outside": {"lat": lat, "lng": lng},
                "reason": "concave_or_area_centroid_outside",
            }
        return {
            "lat": lat,
            "lng": lng,
            "derivation_method": "polygon_area_centroid",
            "inside_polygon": False,
            "needs_review": True,
            "reason": "area_centroid_outside_and_point_on_surface_failed",
        }

    # Degenerate: fall back to first exterior vertex, mark review.
    exterior = _normalize_ring(rings[0])
    if not exterior:
        return {
            "lat": None,
            "lng": None,
            "derivation_method": None,
            "inside_polygon": False,
            "needs_review": True,
            "reason": "degenerate_empty_ring",
        }
    lat, lng = exterior[0][1], exterior[0][0]
    return {
        "lat": lat,
        "lng": lng,
        "derivation_method": "point_on_surface",
        "inside_polygon": point_in_polygon(lat, lng, geom),
        "needs_review": True,
        "reason": "degenerate_zero_area",
    }


def haversine_m(lat1: float, lng1: float, lat2: float, lng2: float) -> float:
    r = 6371000.0
    p1, p2 = math.radians(lat1), math.radians(lat2)
    dp = math.radians(lat2 - lat1)
    dl = math.radians(lng2 - lng1)
    a = math.sin(dp / 2) ** 2 + math.cos(p1) * math.cos(p2) * math.sin(dl / 2) ** 2
    return 2 * r * math.asin(math.sqrt(a))


def lerp(a: float, b: float, t: float) -> float:
    return a + (b - a) * t


def interpolate_representative_points(
    before: dict[str, Any],
    after: dict[str, Any],
    *,
    target_plate: int,
    before_plate: int,
    after_plate: int,
    formula: str,
) -> dict[str, Any]:
    if after_plate == before_plate:
        raise ValueError("cannot interpolate equal plate numbers")
    t = (target_plate - before_plate) / (after_plate - before_plate)
    if not (0.0 <= t <= 1.0):
        raise ValueError(f"interpolation t out of range: {t}")
    lat = lerp(before["representative_lat"], after["representative_lat"], t)
    lng = lerp(before["representative_lng"], after["representative_lng"], t)
    return {
        "lat": round(lat, 7),
        "lng": round(lng, 7),
        "method": "linear_interpolation_between_predial_representative_points",
        "target_plate": target_plate,
        "before_plate": before_plate,
        "after_plate": after_plate,
        "t": round(t, 6),
        "t_in_unit_interval": True,
        "formula": formula,
        "before": before,
        "after": after,
    }
