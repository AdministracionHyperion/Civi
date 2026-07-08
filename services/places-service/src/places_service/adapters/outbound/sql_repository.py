from __future__ import annotations

from sqlalchemy import Boolean, Column, Float, MetaData, String, Table, create_engine, select
from sqlalchemy.engine import Engine

from places_service.shared.catalog import PLACES, Place

metadata = MetaData()

places = Table(
    "places",
    metadata,
    Column("id", String(128), primary_key=True),
    Column("name", String(255), nullable=False),
    Column("address", String(255), nullable=False),
    Column("city", String(128), nullable=False, index=True),
    Column("department", String(128), nullable=False),
    Column("kind", String(32), nullable=False, index=True),
    Column("lat", Float, nullable=False),
    Column("lng", Float, nullable=False),
    Column("is_partner", Boolean, nullable=False, index=True),
)


class SqlPlacesRepository:
    def __init__(self, database_url: str, *, create_schema: bool = False, seed_catalog: bool = False) -> None:
        self.engine: Engine = create_engine(database_url, future=True)
        if create_schema:
            metadata.create_all(self.engine)
        if seed_catalog:
            self._seed_catalog_if_empty()

    def list_all(self) -> list[Place]:
        stmt = select(places).order_by(places.c.city, places.c.name)
        with self.engine.begin() as conn:
            rows = conn.execute(stmt).mappings().all()
        return [_place_from_row(row) for row in rows]

    def list_partners(self) -> list[Place]:
        stmt = (
            select(places)
            .where(places.c.is_partner == True)  # noqa: E712
            .order_by(places.c.city, places.c.name)
        )
        with self.engine.begin() as conn:
            rows = conn.execute(stmt).mappings().all()
        return [_place_from_row(row) for row in rows]

    def _seed_catalog_if_empty(self) -> None:
        with self.engine.begin() as conn:
            existing = conn.execute(select(places.c.id).limit(1)).first()
            if existing is not None:
                return
            conn.execute(
                places.insert(),
                [
                    {
                        "id": place.id,
                        "name": place.name,
                        "address": place.address,
                        "city": place.city,
                        "department": place.department,
                        "kind": place.kind,
                        "lat": place.lat,
                        "lng": place.lng,
                        "is_partner": place.is_partner,
                    }
                    for place in PLACES
                ],
            )


def _place_from_row(row) -> Place:
    return Place(
        id=str(row["id"]),
        name=str(row["name"]),
        address=str(row["address"]),
        city=str(row["city"]),
        department=str(row["department"]),
        kind=str(row["kind"]),
        lat=float(row["lat"]),
        lng=float(row["lng"]),
        is_partner=bool(row["is_partner"]),
    )
