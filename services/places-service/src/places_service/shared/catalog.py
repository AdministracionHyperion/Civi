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
    lat: float
    lng: float
    is_partner: bool = False


PLACES: tuple[Place, ...] = (
    Place(
        id="bga-cda-centro-01",
        name="CDA Centro Bucaramanga",
        address="Bucaramanga, Santander",
        city="Bucaramanga",
        department="Santander",
        kind="CDA",
        lat=7.1193,
        lng=-73.1227,
        is_partner=True,
    ),
    Place(
        id="bga-cia-centro-01",
        name="CIA Bucaramanga Centro",
        address="Bucaramanga, Santander",
        city="Bucaramanga",
        department="Santander",
        kind="CIA",
        lat=7.1151,
        lng=-73.1198,
        is_partner=True,
    ),
    Place(
        id="bog-cda-norte-01",
        name="CDA Norte Bogota",
        address="Bogota, Cundinamarca",
        city="Bogota",
        department="Cundinamarca",
        kind="CDA",
        lat=4.7110,
        lng=-74.0721,
        is_partner=False,
    ),
    Place(
        id="bog-crc-centro-01",
        name="CRC Centro Bogota",
        address="Bogota, Cundinamarca",
        city="Bogota",
        department="Cundinamarca",
        kind="CRC",
        lat=4.6097,
        lng=-74.0817,
        is_partner=False,
    ),
    Place(
        id="med-cea-centro-01",
        name="CEA Medellin Centro",
        address="Medellin, Antioquia",
        city="Medellin",
        department="Antioquia",
        kind="CEA",
        lat=6.2442,
        lng=-75.5812,
        is_partner=False,
    ),
)
