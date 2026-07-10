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
        id="flo-cda-florida-02",
        name="CDA La Florida Floridablanca",
        address="Calle 5 #10-90, Florida, Floridablanca",
        city="Floridablanca",
        department="Santander",
        kind="CDA",
        lat=7.0622,
        lng=-73.0860,
        is_partner=True,
    ),
    Place(
        id="flo-cda-fosuna-03",
        name="CDA Fosuna Floridablanca",
        address="Autopista Floridablanca Km 2, Floridablanca",
        city="Floridablanca",
        department="Santander",
        kind="CDA",
        lat=7.0750,
        lng=-73.1150,
        is_partner=True,
    ),
    Place(
        id="flo-cda-metroauto-04",
        name="CDA Metroauto Floridablanca",
        address="Anillo Vial Km 8, Floridablanca",
        city="Floridablanca",
        department="Santander",
        kind="CDA",
        lat=7.0680,
        lng=-73.1003,
        is_partner=True,
    ),
    Place(
        id="pie-cda-autopista-05",
        name="CDA Autopista Piedecuesta",
        address="Km 12 via Floridablanca-Piedecuesta, Piedecuesta",
        city="Piedecuesta",
        department="Santander",
        kind="CDA",
        lat=6.9878,
        lng=-73.0500,
        is_partner=True,
    ),
    Place(
        id="flo-cda-tecniFlo-06",
        name="CDA Floridablanca Centro",
        address="Carrera 8 #12-45, Centro, Floridablanca",
        city="Floridablanca",
        department="Santander",
        kind="CDA",
        lat=7.0640,
        lng=-73.0885,
        is_partner=False,
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
