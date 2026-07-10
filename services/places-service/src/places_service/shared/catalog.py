from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True)
class Place:
    id: str
    name: str
    address: str
    city: str
    department: str
    kind: str
    lat: float | None = None
    lng: float | None = None
    is_partner: bool = False
    phone: str | None = None
    status: str = "unknown"
    source: str = "catalog"
    source_updated_at: str | None = None
    geocode_confidence: float | None = None
    geocode_provider: str | None = None
    geocode_status: str = "skipped"
    runt_actor_id: str | None = None
    nit: str | None = None
    is_bookable: bool = False
    booking_mode: str = "information_only"
    municipality_code: str | None = None
    status_verified: bool = False
    location_precision: str | None = None


# Sample fixtures for unit tests / explicit sample bootstrap only — not production catalog.
PLACES: tuple[Place, ...] = (
    Place(
        id="bga-cda-centro-01",
        name="CDA Centro Bucaramanga",
        address="Calle 36 # 15-20",
        city="Bucaramanga",
        department="Santander",
        kind="CDA",
        lat=7.1193,
        lng=-73.1227,
        is_partner=True,
        is_bookable=True,
        booking_mode="civi",
        status="unknown",
        geocode_status="ok",
        geocode_provider="manual",
        municipality_code="68001",
    ),
    Place(
        id="bga-cia-centro-01",
        name="CIA Bucaramanga Centro",
        address="Carrera 27 # 34-10",
        city="Bucaramanga",
        department="Santander",
        kind="CIA",
        lat=7.1151,
        lng=-73.1198,
        is_partner=True,
        is_bookable=True,
        booking_mode="civi",
        status="unknown",
        geocode_status="ok",
        geocode_provider="manual",
        municipality_code="68001",
    ),
    Place(
        id="bog-cda-norte-01",
        name="CDA Norte Bogota",
        address="Calle 100 # 19-50",
        city="Bogota",
        department="Bogota D.C.",
        kind="CDA",
        lat=4.7110,
        lng=-74.0721,
        is_partner=False,
        is_bookable=False,
        booking_mode="information_only",
        status="unknown",
        geocode_status="ok",
        geocode_provider="manual",
        municipality_code="11001",
    ),
    Place(
        id="bog-crc-centro-01",
        name="CRC Centro Bogota",
        address="Carrera 7 # 32-16",
        city="Bogota",
        department="Bogota D.C.",
        kind="CRC",
        lat=4.6097,
        lng=-74.0817,
        is_partner=False,
        is_bookable=False,
        booking_mode="information_only",
        status="unknown",
        geocode_status="ok",
        geocode_provider="manual",
        municipality_code="11001",
    ),
    Place(
        id="med-cea-centro-01",
        name="CEA Medellin Centro",
        address="Calle 50 # 45-20",
        city="Medellin",
        department="Antioquia",
        kind="CEA",
        lat=6.2442,
        lng=-75.5812,
        is_partner=False,
        is_bookable=False,
        booking_mode="information_only",
        status="unknown",
        geocode_status="ok",
        geocode_provider="manual",
        municipality_code="05001",
    ),
)
