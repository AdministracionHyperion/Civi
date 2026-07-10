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


def ring_signed_area(ring: list[list[float]] | list[tuple[float, float]]) -> float:
    """Signed area of a ring (x=lng, y=lat). Positive ≈ counterclockwise."""
    part = _ring_signed_area_and_centroid(ring)
    return 0.0 if part is None else part[0]


def classify_esri_rings(
    geom: dict[str, Any],
) -> list[dict[str, Any]]:
    """Group Esri rings into exterior polygons with holes (multipart-safe).

    Does not assume rings[0] is the only exterior. A ring is nested in another
    if a representative vertex lies inside that other ring. Top-level rings
    (not nested) are exteriors; rings nested in an exterior are holes.
    Orientation (CW/CCW) is recorded but nesting decides the role.
    """
    rings_raw = geom.get("rings") or []
    prepared: list[dict[str, Any]] = []
    for idx, ring in enumerate(rings_raw):
        pts = _normalize_ring(ring)
        if len(pts) < 3:
            prepared.append(
                {
                    "index": idx,
                    "pts": pts,
                    "degenerate": True,
                    "signed_area": 0.0,
                    "orientation": "degenerate",
                }
            )
            continue
        area = ring_signed_area(pts)
        prepared.append(
            {
                "index": idx,
                "pts": pts,
                "degenerate": abs(area) < AREA_EPS,
                "signed_area": area,
                "orientation": "ccw" if area > 0 else "cw",
            }
        )

    def _contains(outer_pts: list[tuple[float, float]], inner_pts: list[tuple[float, float]]) -> bool:
        if len(outer_pts) < 3 or len(inner_pts) < 3:
            return False
        # Test first vertex of inner against outer ring only.
        x, y = inner_pts[0]
        return _point_in_ring(x, y, outer_pts)

    n = len(prepared)
    parent = [-1] * n
    for i in range(n):
        if prepared[i]["degenerate"]:
            continue
        best_j = -1
        best_abs_area = None
        for j in range(n):
            if i == j or prepared[j]["degenerate"]:
                continue
            if not _contains(prepared[j]["pts"], prepared[i]["pts"]):
                continue
            abs_area = abs(prepared[j]["signed_area"])
            # Choose the smallest enclosing ring as direct parent.
            if best_abs_area is None or abs_area < best_abs_area:
                best_abs_area = abs_area
                best_j = j
        parent[i] = best_j

    exteriors: list[dict[str, Any]] = []
    exterior_index_map: dict[int, int] = {}
    for i, ring in enumerate(prepared):
        if ring["degenerate"]:
            continue
        if parent[i] == -1:
            exterior_index_map[i] = len(exteriors)
            exteriors.append(
                {
                    "exterior_index": ring["index"],
                    "exterior": ring["pts"],
                    "orientation": ring["orientation"],
                    "holes": [],
                    "hole_indices": [],
                }
            )

    for i, ring in enumerate(prepared):
        if ring["degenerate"] or parent[i] == -1:
            continue
        # Walk up to top-level exterior.
        p = parent[i]
        while p != -1 and parent[p] != -1:
            p = parent[p]
        if p == -1 or p not in exterior_index_map:
            continue
        # Direct children of an exterior are holes; deeper nesting (island in hole)
        # is treated as additional exterior content via even-odd PIP.
        if parent[i] == p:
            ext = exteriors[exterior_index_map[p]]
            ext["holes"].append(ring["pts"])
            ext["hole_indices"].append(ring["index"])

    return exteriors


def point_in_polygon(lat: float, lng: float, geom: dict[str, Any]) -> bool:
    """True if (lat,lng) is in the filled region of an Esri (multi)polygon.

    Uses even-odd fill across all non-degenerate rings so that:
    - multiple exterior parts are supported;
    - holes punch out of their containing exterior;
    - CW/CCW orientation does not matter;
    - rings[0] is not assumed to be the sole exterior.
    """
    rings = geom.get("rings") or []
    if not rings:
        return False
    x, y = lng, lat
    inside = False
    for ring in rings:
        pts = _normalize_ring(ring)
        if len(pts) < 3:
            continue
        if abs(ring_signed_area(pts)) < AREA_EPS:
            continue
        if _point_in_ring(x, y, pts):
            inside = not inside
    return inside


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
    """Deterministic interior point: midpoint of the longest interior scan segment.

    Scans each exterior part (multipart-aware). Falls back to combined bbox.
    """
    parts = classify_esri_rings(geom)
    scan_targets: list[list[tuple[float, float]]] = [p["exterior"] for p in parts] if parts else []
    if not scan_targets:
        rings = geom.get("rings") or []
        for ring in rings:
            pts = _normalize_ring(ring)
            if len(pts) >= 3 and abs(ring_signed_area(pts)) >= AREA_EPS:
                scan_targets.append(pts)
    if not scan_targets:
        return None

    best: tuple[float, float, float] | None = None  # (length, x, y)
    for exterior in scan_targets:
        xmin, ymin, xmax, ymax = _bbox(exterior)
        if abs(ymax - ymin) < COORD_EPS or abs(xmax - xmin) < COORD_EPS:
            cand = (exterior[0][1], exterior[0][0])
            if point_in_polygon(cand[0], cand[1], geom):
                return cand
            continue
        for i in range(scan_lines):
            y = ymin + (i + 0.5) * (ymax - ymin) / scan_lines
            # Intersect against ALL rings so holes are respected (even-odd pairing).
            xs: list[float] = []
            for ring in geom.get("rings") or []:
                pts = _normalize_ring(ring)
                if len(pts) < 3:
                    continue
                xs.extend(_horizontal_intersections(y, pts))
            xs.sort()
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
