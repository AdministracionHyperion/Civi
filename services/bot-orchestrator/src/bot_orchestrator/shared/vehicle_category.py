from __future__ import annotations

import re
import unicodedata


CLASE_TO_QUOTE_CATEGORY: dict[str, str] = {
    "MOTOCICLETA": "moto",
    "MOTOCARRO": "moto",
    "MOTOTRICICLO": "moto",
    "CUATRIMOTO": "moto",
    "AUTOMOVIL": "carro",
    "CAMPERO": "campero",
    "CAMIONETA": "camioneta",
    "CAMIONETA DE SERVICIO PUBLICO": "taxi",
    "TAXI": "taxi",
    "MICROBUS": "bus",
    "BUS": "bus",
    "BUSETA": "bus",
    "CAMION": "camion",
    "TRACTOCAMION": "camion",
    "VOLQUETA": "camion",
    "TRANSPORTE DE CARGA": "camion",
}

KEYWORD_CATEGORY_ORDER: tuple[tuple[str, str], ...] = (
    ("MOTO", "moto"),
    ("CUATRIMOTO", "moto"),
    ("TAXI", "taxi"),
    ("SERVICIO PUBLICO", "taxi"),
    ("CAMPERO", "campero"),
    ("CAMIONETA", "camioneta"),
    ("SUV", "camioneta"),
    ("MICROBUS", "bus"),
    ("BUSETA", "bus"),
    ("BUS", "bus"),
    ("TRACTOCAMION", "camion"),
    ("VOLQUETA", "camion"),
    ("CAMION", "camion"),
    ("CARGA", "camion"),
    ("AUTOMOVIL", "carro"),
    ("PARTICULAR", "carro"),
)


def map_clase_to_quote_category(clase_vehiculo: object) -> str | None:
    if not isinstance(clase_vehiculo, str) or not clase_vehiculo.strip():
        return None
    folded = _fold(clase_vehiculo)
    if not folded:
        return None
    if folded in CLASE_TO_QUOTE_CATEGORY:
        return CLASE_TO_QUOTE_CATEGORY[folded]
    for keyword, category in KEYWORD_CATEGORY_ORDER:
        if keyword in folded:
            return category
    return None


def _fold(value: str) -> str:
    stripped = unicodedata.normalize("NFKD", value)
    ascii_value = "".join(char for char in stripped if not unicodedata.combining(char))
    return re.sub(r"\s+", " ", ascii_value).strip().upper()
