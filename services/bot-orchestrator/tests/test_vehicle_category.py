from __future__ import annotations

from bot_orchestrator.shared.vehicle_category import map_clase_to_quote_category


def test_maps_runt_vehicle_class_to_quote_category() -> None:
    assert map_clase_to_quote_category("MOTOCICLETA") == "moto"
    assert map_clase_to_quote_category("AUTOMOVIL") == "carro"
    assert map_clase_to_quote_category("CAMIONETA") == "camioneta"
    assert map_clase_to_quote_category("Automovil de servicio publico") == "taxi"
    assert map_clase_to_quote_category("TRACTOCAMION") == "camion"


def test_unknown_vehicle_class_returns_none() -> None:
    assert map_clase_to_quote_category("") is None
    assert map_clase_to_quote_category(None) is None
    assert map_clase_to_quote_category("MAQUINARIA INDUSTRIAL") is None
