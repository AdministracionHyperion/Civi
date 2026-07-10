from __future__ import annotations

import json
import re
import unicodedata
from dataclasses import dataclass
from functools import lru_cache
from pathlib import Path
from typing import Any

REFERENCE_YEAR = 2026


class QuoteError(ValueError):
    pass


def format_cop(value: int) -> str:
    return f"${value:,.0f}".replace(",", ".")


SOAT_TARIFFS_COP: dict[str, list[tuple[int, int, int, int]]] = {
    "moto": [
        (1, 100, 256_200, 256_200),
        (101, 200, 343_300, 343_300),
        (201, 9999, 761_400, 761_400),
    ],
    "carro": [
        (0, 1500, 447_300, 592_900),
        (1501, 2500, 544_700, 677_400),
        (2501, 9999, 636_000, 754_300),
    ],
    "campero": [
        (0, 1500, 792_800, 953_000),
        (1501, 2500, 946_600, 1_121_400),
        (2501, 9999, 1_110_300, 1_274_000),
    ],
    "taxi": [
        (0, 1500, 281_900, 352_000),
        (1501, 2500, 350_000, 432_400),
        (2501, 9999, 451_400, 529_300),
    ],
}

SOAT_ALIASES = {
    "moto": "moto",
    "motocicleta": "moto",
    "scooter": "moto",
    "carro": "carro",
    "auto": "carro",
    "automovil": "carro",
    "vehiculo": "carro",
    "particular": "carro",
    "camioneta": "campero",
    "campero": "campero",
    "suv": "campero",
    "4x4": "campero",
    "taxi": "taxi",
}


def quote_soat(*, vehicle_type: str, cilindraje: int, modelo: int, year: int | None = None) -> dict[str, object]:
    tipo = _normalize_alias(vehicle_type, SOAT_ALIASES, "tipo de vehiculo")
    if cilindraje <= 0 or cilindraje > 9999:
        raise QuoteError("Cilindraje invalido para SOAT.")
    ref_year = year or REFERENCE_YEAR
    if modelo < 1950 or modelo > ref_year + 1:
        raise QuoteError("Modelo invalido para SOAT.")

    age_years = max(0, ref_year - modelo)
    is_old = age_years >= 10
    for cc_min, cc_max, price_new, price_old in SOAT_TARIFFS_COP[tipo]:
        if cc_min <= cilindraje <= cc_max:
            price = price_new if tipo == "moto" or not is_old else price_old
            range_label = _format_cc_range(cc_min, cc_max)
            return {
                "quote_type": "exact",
                "service_type": "soat",
                "price_cop": price,
                "price_min": price,
                "price_max": price,
                "details": {
                    "tipo": tipo,
                    "cilindraje": cilindraje,
                    "modelo": modelo,
                    "age_years": age_years,
                    "age_category": "OLD" if is_old else "NEW",
                    "range_label": range_label,
                    "reference_year": ref_year,
                },
                "message": (
                    f"SOAT {tipo} {range_label}, modelo {modelo}: "
                    f"{format_cop(price)} COP referencial {ref_year}."
                ),
            }
    raise QuoteError("Cilindraje fuera de la tabla SOAT.")


TECNO_TARIFFS_COP: dict[str, int] = {
    "moto": 247_490,
    "liviano_particular": 368_853,
    "liviano_publico": 371_000,
    "pesado_particular": 519_000,
    "pesado_publico": 521_000,
    "biarticulado": 583_000,
}

TECNO_ALIASES = {
    "moto": "moto",
    "motocicleta": "moto",
    "scooter": "moto",
    "carro": "liviano_particular",
    "auto": "liviano_particular",
    "automovil": "liviano_particular",
    "particular": "liviano_particular",
    "carro particular": "liviano_particular",
    "camioneta": "liviano_particular",
    "suv": "liviano_particular",
    "campero": "liviano_particular",
    "taxi": "liviano_publico",
    "publico": "liviano_publico",
    "carro publico": "liviano_publico",
    "camion": "pesado_particular",
    "bus": "pesado_particular",
    "buseta": "pesado_particular",
    "pesado": "pesado_particular",
    "camion publico": "pesado_publico",
    "bus publico": "pesado_publico",
    "biarticulado": "biarticulado",
    "transmilenio": "biarticulado",
    "brt": "biarticulado",
}

TECNO_HUMAN = {
    "moto": "moto",
    "liviano_particular": "carro particular",
    "liviano_publico": "vehiculo de servicio publico",
    "pesado_particular": "vehiculo pesado particular",
    "pesado_publico": "vehiculo pesado publico",
    "biarticulado": "biarticulado",
}


def quote_tecnomecanica(*, category: str) -> dict[str, object]:
    categoria = _normalize_alias(category, TECNO_ALIASES, "categoria")
    price = TECNO_TARIFFS_COP[categoria]
    human = TECNO_HUMAN[categoria]
    return {
        "quote_type": "exact",
        "service_type": "tecnomecanica",
        "price_cop": price,
        "price_min": price,
        "price_max": price,
        "details": {"categoria": categoria, "categoria_human": human, "reference_year": REFERENCE_YEAR},
        "message": (
            f"Tecnomecanica para {human} {REFERENCE_YEAR}: alrededor de "
            f"{format_cop(price)} COP. Es referencial; el CDA confirma el valor final."
        ),
    }


CATEGORY_AMOUNT_COP = {
    "A": 233_456,
    "B": 466_912,
    "C": 875_460,
    "D": 1_750_920,
    "E": 2_626_380,
    "F": 58_364,
    "H": 291_820,
}

SMDLV_BY_YEAR = {2026: 58_364}
CATEGORY_SMDLV = {"A": 4, "B": 8, "C": 15, "D": 30, "E": 45, "F": 1, "H": 5}


@dataclass(frozen=True)
class InfraccionSpec:
    codigo: str
    categoria: str
    smdlv: int
    descripcion: str
    articulo: str
    admite_descuento_curso: bool
    aliases: tuple[str, ...]
    variables: tuple[dict[str, Any], ...]
    monto_cop_2026: int | None

    @classmethod
    def from_dict(cls, row: dict[str, Any]) -> InfraccionSpec:
        variables = tuple(row.get("variables") or ())
        smdlv = int(row.get("smdlv") or 0)
        if variables and not smdlv:
            smdlv = int(variables[0].get("smdlv") or 0)
        monto = row.get("monto_cop_2026")
        return cls(
            codigo=str(row["codigo"]).upper(),
            categoria=str(row["categoria"]).upper(),
            smdlv=smdlv,
            descripcion=str(row["descripcion_oficial"]),
            articulo=str(row.get("articulo") or "Art. 131 Ley 769/2002"),
            admite_descuento_curso=bool(row.get("admite_descuento_curso", True)),
            aliases=tuple(str(value) for value in row.get("aliases") or ()),
            variables=variables,
            monto_cop_2026=int(monto) if monto is not None else None,
        )


@dataclass(frozen=True)
class InfraccionMatch:
    spec: InfraccionSpec
    score: float


def quote_infraccion(
    *,
    consulta: str = "",
    codigo: str | None = None,
    variable: str | None = None,
    year: int | None = None,
) -> dict[str, object]:
    yr = year or REFERENCE_YEAR
    spec = _find_infraccion(consulta=consulta, codigo=codigo)
    if isinstance(spec, list):
        return {
            "quote_type": "needs_clarification",
            "service_type": "infraccion",
            "price_min": 0,
            "price_max": 0,
            "options": [
                {"codigo": item.spec.codigo, "descripcion": item.spec.descripcion, "score": item.score}
                for item in spec[:3]
            ],
            "message": "Encontre varias infracciones posibles. Dime el codigo o describe mejor cual aplica.",
        }

    if spec.variables and not variable:
        return {
            "quote_type": "needs_clarification",
            "service_type": "infraccion",
            "price_min": 0,
            "price_max": 0,
            "details": {"codigo": spec.codigo, "variables": list(spec.variables)},
            "message": "Esa infraccion tiene rangos. Dime cual aplica para calcular el valor.",
        }

    chosen_variable = None
    smdlv = spec.smdlv
    if spec.variables:
        chosen_variable = next((item for item in spec.variables if item.get("id") == variable), None)
        if not chosen_variable:
            raise QuoteError("Variable no valida para esa infraccion.")
        smdlv = int(chosen_variable.get("smdlv") or 0)

    amount = spec.monto_cop_2026 if spec.monto_cop_2026 is not None and not chosen_variable else _valor_cop(
        smdlv, categoria=spec.categoria, year=yr
    )
    amount_50 = amount // 2 if spec.admite_descuento_curso and amount > 0 else None
    amount_25 = (amount * 3) // 4 if spec.admite_descuento_curso and amount > 0 else None
    message = (
        f"Infraccion {spec.codigo} categoria {spec.categoria}: {format_cop(amount)} COP "
        f"referencial {yr}. {spec.descripcion}"
    )
    if amount_50 is not None:
        message += f" Con 50% seria {format_cop(amount_50)} COP mas curso CIA aparte."
    elif not spec.admite_descuento_curso:
        message += " Generalmente no admite descuento por curso pedagogico."
    return {
        "quote_type": "exact",
        "service_type": "infraccion",
        "price_cop": amount,
        "price_min": amount,
        "price_max": amount,
        "details": {
            "codigo": spec.codigo,
            "categoria": spec.categoria,
            "descripcion": spec.descripcion,
            "articulo": spec.articulo,
            "smdlv": smdlv,
            "admite_descuento_curso": spec.admite_descuento_curso,
            "monto_50pct": amount_50,
            "monto_25pct": amount_25,
            "variable": chosen_variable,
            "reference_year": yr,
        },
        "message": message,
    }


def quote_course() -> dict[str, object]:
    price = 329_000
    return {
        "quote_type": "exact",
        "service_type": "curso_multa",
        "price_cop": price,
        "price_min": price,
        "price_max": price,
        "details": {"reference_year": REFERENCE_YEAR},
        "message": (
            f"El curso pedagogico CIA ronda {format_cop(price)} COP en {REFERENCE_YEAR}. "
            "Ese valor es aparte del comparendo."
        ),
    }


def generic_band(service_type: str) -> dict[str, object]:
    bands = {
        "soat": (350_000, 1_200_000),
        "tecnomecanica": (180_000, 350_000),
        "mecanico": (90_000, 450_000),
        "licencia": (250_000, 650_000),
    }
    price_min, price_max = bands.get(service_type, (100_000, 500_000))
    return {
        "quote_type": "range",
        "service_type": service_type,
        "price_min": price_min,
        "price_max": price_max,
        "message": "",
    }


def _normalize_alias(raw: str, aliases: dict[str, str], label: str) -> str:
    norm = _normalize_text(raw)
    if norm in aliases:
        return aliases[norm]
    for alias in sorted(aliases, key=len, reverse=True):
        if alias in norm:
            return aliases[alias]
    raise QuoteError(f"{label} no soportado.")


def _format_cc_range(cc_min: int, cc_max: int) -> str:
    if cc_max >= 9999:
        return f"{cc_min}+ cc"
    if cc_min == 0:
        return f"hasta {cc_max} cc"
    return f"{cc_min}-{cc_max} cc"


def _valor_cop(smdlv: int, *, categoria: str, year: int) -> int:
    official = CATEGORY_AMOUNT_COP.get(categoria.upper()) if year == REFERENCE_YEAR else None
    cat_units = CATEGORY_SMDLV.get(categoria.upper())
    if official is not None and cat_units == smdlv:
        return official
    return smdlv * SMDLV_BY_YEAR.get(year, SMDLV_BY_YEAR[REFERENCE_YEAR])


def _find_infraccion(*, consulta: str, codigo: str | None) -> InfraccionSpec | list[InfraccionMatch]:
    if codigo:
        spec = _by_codigo().get(codigo.strip().upper())
        if not spec:
            raise QuoteError("Codigo de infraccion no encontrado.")
        return spec
    text = consulta or ""
    if _is_only_fotomulta(text):
        raise QuoteError("Fotomulta es el medio; necesito saber la infraccion concreta.")
    detected = _detect_codigo(text)
    if detected:
        spec = _by_codigo().get(detected)
        if spec:
            return spec
    matches = _search_infracciones(text)
    if not matches:
        raise QuoteError("No encontre esa infraccion en el catalogo CNT.")
    if len(matches) > 1 and matches[0].score - matches[1].score < 0.08:
        return matches[:3]
    return matches[0].spec


CODIGO_RE = re.compile(r"\b([A-I]\d{2})\b", re.IGNORECASE)


def _detect_codigo(text: str) -> str | None:
    match = CODIGO_RE.search(text or "")
    return match.group(1).upper() if match else None


def _is_only_fotomulta(text: str) -> bool:
    normalized = _normalize_text(text)
    return (
        normalized in {"fotomulta", "foto multa", "comparendo electronico"}
        or ("fotomulta" in normalized and not any(term in normalized for term in ("semaforo", "velocidad", "parqueo", "soat", "cinturon", "celular", "embriaguez", "pico")))
    )


def _search_infracciones(query: str, *, limit: int = 5) -> list[InfraccionMatch]:
    normalized = _normalize_text(query)
    if not normalized:
        return []
    matches: list[InfraccionMatch] = []
    for spec in load_infracciones():
        score = _score_infraccion(normalized, spec)
        if score >= 0.35:
            matches.append(InfraccionMatch(spec=spec, score=score))
    matches.sort(key=lambda item: (-item.score, item.spec.codigo))
    return matches[:limit]


def _score_infraccion(query: str, spec: InfraccionSpec) -> float:
    desc = _normalize_text(spec.descripcion)
    score = 0.0
    if query in desc:
        score = 0.95
    else:
        best = 0.0
        for alias in spec.aliases:
            alias_norm = _normalize_text(alias)
            if not alias_norm:
                continue
            if query == alias_norm or query in alias_norm or alias_norm in query:
                score = 0.92
                break
            best = max(best, _token_overlap(query, alias_norm))
        else:
            score = max(best, _token_overlap(query, desc) * 0.85)

    # Prefer C14 over A08 for vehicle/moto/pico-y-placa contexts.
    vehicle_context = any(
        term in query
        for term in ("moto", "carro", "auto", "vehiculo", "pico", "placa", "carrera", "avenida")
    )
    pedestrian_context = any(term in query for term in ("peaton", "ciclista", "bicicleta", "bici"))
    if spec.codigo == "C14" and vehicle_context and not pedestrian_context:
        score += 0.08
    if spec.codigo == "A08" and vehicle_context and not pedestrian_context:
        score -= 0.08
    return score


def _token_overlap(left: str, right: str) -> float:
    left_tokens = set(left.split())
    right_tokens = set(right.split())
    if not left_tokens or not right_tokens:
        return 0.0
    return len(left_tokens & right_tokens) / len(left_tokens | right_tokens)


def _normalize_text(text: str | None) -> str:
    value = unicodedata.normalize("NFD", (text or "").lower())
    value = "".join(char for char in value if unicodedata.category(char) != "Mn")
    value = re.sub(r"[^a-z0-9\s]", " ", value)
    return re.sub(r"\s+", " ", value).strip()


@lru_cache(maxsize=1)
def load_infracciones() -> tuple[InfraccionSpec, ...]:
    path = Path(__file__).resolve().parents[1] / "data" / "infracciones_cnt.json"
    raw = json.loads(path.read_text(encoding="utf-8"))
    return tuple(InfraccionSpec.from_dict(row) for row in raw.get("infracciones") or [])


@lru_cache(maxsize=1)
def _by_codigo() -> dict[str, InfraccionSpec]:
    return {spec.codigo: spec for spec in load_infracciones()}
