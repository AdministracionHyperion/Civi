from __future__ import annotations

"""City / metro rollout scopes for validated geocode imports.

Manizales remains a single-municipality scope. Santander validates each row
against the bbox of its own municipality (never a single metro envelope that
would hide cross-municipality mistakes).
"""

from dataclasses import dataclass
from pathlib import Path
import unicodedata

from places_service.geocoding.bounds import (
    BBox,
    BUCARAMANGA_BBOX,
    BUCARAMANGA_CENTROID,
    FLORIDABLANCA_BBOX,
    GIRON_BBOX,
    MANIZALES_BBOX,
    MANIZALES_CENTROID,
    PIEDECUESTA_BBOX,
)


def fold_place_name(value: str) -> str:
    """Casefold + strip accents for municipality / department matching."""
    normalized = unicodedata.normalize("NFKD", (value or "").strip())
    without_marks = "".join(ch for ch in normalized if not unicodedata.combining(ch))
    return without_marks.casefold()


@dataclass(frozen=True)
class MunicipalityScope:
    name: str
    aliases: frozenset[str]
    bbox: BBox

    def matches(self, city: str) -> bool:
        return fold_place_name(city) in self.aliases


@dataclass(frozen=True)
class GeocodeScope:
    key: str
    display_name: str
    expected_country: str
    expected_department: str
    municipalities: tuple[MunicipalityScope, ...]
    attempt_source: str
    default_input: Path
    default_report: Path
    centroid: tuple[float, float] | None = None
    # When set, outside-bbox reasons use this exact prefix (Manizales compat).
    # Otherwise reasons are ``outside_municipality_bbox:{Name}:{lat},{lng}``.
    outside_bbox_prefix: str | None = None

    def resolve_municipality(self, city: str) -> MunicipalityScope | None:
        folded = fold_place_name(city)
        for muni in self.municipalities:
            if folded in muni.aliases:
                return muni
        return None

    def municipality_names(self) -> frozenset[str]:
        return frozenset(m.name for m in self.municipalities)


MANIZALES_SCOPE = GeocodeScope(
    key="manizales",
    display_name="Manizales",
    expected_country="colombia",
    expected_department="caldas",
    municipalities=(
        MunicipalityScope(
            name="Manizales",
            aliases=frozenset({"manizales"}),
            bbox=MANIZALES_BBOX,
        ),
    ),
    attempt_source="manizales_validated_geocode",
    default_input=Path(
        "services/places-service/data/geocodes/manizales/geocodes_manizales_validado.csv"
    ),
    default_report=Path(
        "services/places-service/data/reports/manizales_geocode_import_report.json"
    ),
    centroid=MANIZALES_CENTROID,
    outside_bbox_prefix="outside_manizales_bbox",
)

SANTANDER_SCOPE = GeocodeScope(
    key="santander",
    display_name="Santander (área metropolitana priorizada)",
    expected_country="colombia",
    expected_department="santander",
    municipalities=(
        MunicipalityScope(
            name="Bucaramanga",
            aliases=frozenset({"bucaramanga"}),
            bbox=BUCARAMANGA_BBOX,
        ),
        MunicipalityScope(
            name="Floridablanca",
            aliases=frozenset({"floridablanca"}),
            bbox=FLORIDABLANCA_BBOX,
        ),
        MunicipalityScope(
            name="Giron",
            aliases=frozenset({"giron"}),  # folded; matches Girón / Giron
            bbox=GIRON_BBOX,
        ),
        MunicipalityScope(
            name="Piedecuesta",
            aliases=frozenset({"piedecuesta"}),
            bbox=PIEDECUESTA_BBOX,
        ),
    ),
    attempt_source="santander_validated_geocode",
    default_input=Path(
        "services/places-service/data/geocodes/santander/"
        "geocodes_santander_priorizado_validado.csv"
    ),
    default_report=Path(
        "services/places-service/data/reports/santander_geocode_import_report.json"
    ),
    centroid=BUCARAMANGA_CENTROID,
    outside_bbox_prefix=None,
)

SCOPES: dict[str, GeocodeScope] = {
    MANIZALES_SCOPE.key: MANIZALES_SCOPE,
    SANTANDER_SCOPE.key: SANTANDER_SCOPE,
}


__all__ = [
    "MunicipalityScope",
    "GeocodeScope",
    "MANIZALES_SCOPE",
    "SANTANDER_SCOPE",
    "SCOPES",
    "fold_place_name",
]
