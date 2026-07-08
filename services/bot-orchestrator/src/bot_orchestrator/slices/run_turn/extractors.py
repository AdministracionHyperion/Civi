from __future__ import annotations

import re
import unicodedata

PLATE_RE = re.compile(r"\b([A-Z]{3}\s?\d{2}[A-Z0-9]|[A-Z]{3}\s?\d{3})\b", re.IGNORECASE)
DOCUMENT_RE = re.compile(
    r"(?:cedula|c[eé]dula|documento|cc|doc)\D{0,12}([0-9][0-9.\-\s]{3,18}[0-9])",
    re.IGNORECASE,
)
LOOSE_DOCUMENT_RE = re.compile(r"\b([0-9]{6,12})\b")
CITY_RE = re.compile(r"\b(bucaramanga|bogota|bogotá|medellin|medellín|manizales|cali)\b", re.IGNORECASE)
ISO_DATE_RE = re.compile(r"\b(20\d{2}-\d{2}-\d{2})(?:[ T](\d{2}:\d{2}))?\b")
DISPLACEMENT_RE = re.compile(r"\b([1-9][0-9]{1,3})\s*(?:cc|c\.c\.|cilindraje)?\b", re.IGNORECASE)
MODEL_RE = re.compile(r"\b(19[5-9][0-9]|20[0-3][0-9])\b")
INFRACTION_CODE_RE = re.compile(r"\b([A-I]\d{2})\b", re.IGNORECASE)
APPOINTMENT_ID_RE = re.compile(r"\b(?:cita|reserva|turno)?\s*#?\s*(\d{1,9})\b", re.IGNORECASE)


def extract_plate(text: str) -> str | None:
    match = PLATE_RE.search(text or "")
    if not match:
        return None
    return match.group(1).replace(" ", "").upper()


def extract_document(text: str) -> str | None:
    raw = text or ""
    match = DOCUMENT_RE.search(raw)
    if match:
        return re.sub(r"\D", "", match.group(1))
    loose = LOOSE_DOCUMENT_RE.search(raw)
    if loose:
        return loose.group(1)
    return None


def wants_vigencia(text: str) -> bool:
    lowered = (text or "").lower()
    terms = ("soat", "tecno", "tecnico", "técnico", "tecnomecanica", "tecnomecánica", "rtm", "vigencia", "vence", "vencimiento")
    return any(term in lowered for term in terms)


def wants_infraccion_quote(text: str) -> bool:
    lowered = (text or "").lower()
    value_terms = ("cuanto vale", "cuánto vale", "cuanto cuesta", "cuánto cuesta", "cuanto es", "qué cuesta", "que cuesta", "valor", "precio", "costo", "tarifa")
    infraction_terms = (
        "multa por",
        "comparendo por",
        "infraccion por",
        "infracción por",
        "infraccion",
        "infracción",
        "semaforo",
        "semáforo",
        "velocidad",
        "mal parqueo",
        "parqueo",
        "cinturon",
        "cinturón",
        "celular",
        "embriaguez",
        "pico y placa",
    )
    personal_terms = ("mis multas", "mis comparendos", "mi multa", "mi comparendo", "cuanto debo", "cuánto debo")
    return (
        any(term in lowered for term in value_terms)
        and any(term in lowered for term in infraction_terms)
        and not any(term in lowered for term in personal_terms)
    )


def wants_multas(text: str) -> bool:
    lowered = (text or "").lower()
    if wants_infraccion_quote(text):
        return False
    terms = ("multa", "multas", "comparendo", "comparendos", "simit", "fotomulta")
    return any(term in lowered for term in terms)


def wants_runt_profile(text: str) -> bool:
    lowered = (text or "").lower()
    if any(term in lowered for term in ("agendar", "agenda", "cita", "reservar", "cotizar", "precio")):
        return False
    terms = (
        "perfil runt",
        "runt por cedula",
        "runt por cédula",
        "mi runt",
        "mis licencias",
        "mi licencia",
        "estado de licencia",
        "categoria de licencia",
        "categoría de licencia",
        "categorias de licencia",
        "categorías de licencia",
        "puntos de licencia",
        "puntos en licencia",
        "perfil conductor",
        "perfil de conductor",
    )
    return any(term in lowered for term in terms)


def wants_soat(text: str) -> bool:
    return "soat" in (text or "").lower()


def wants_tecno(text: str) -> bool:
    lowered = (text or "").lower()
    return any(term in lowered for term in ("tecno", "tecnomecanica", "tecnomecánica", "rtm", "tecnico", "técnico"))


def wants_appointment(text: str) -> bool:
    lowered = (text or "").lower()
    return any(term in lowered for term in ("cita", "agendar", "agenda", "turno", "reservar"))


def wants_cancel_appointment(text: str) -> bool:
    lowered = (text or "").lower()
    return any(term in lowered for term in ("cancelar", "cancela", "cancelame", "anular", "eliminar")) and any(
        term in lowered for term in ("cita", "turno", "reserva")
    )


def wants_reminder(text: str) -> bool:
    lowered = (text or "").lower()
    return any(term in lowered for term in ("recordatorio", "recordame", "recuérdame", "recuerdame", "avisame", "avísame"))


def wants_alternative_places(text: str) -> bool:
    normalized = _normalized(text)
    return any(
        term in normalized
        for term in (
            "otra opcion",
            "otras opciones",
            "alternativa",
            "alternativas",
            "mas opciones",
            "no me sirve",
            "no ese",
            "ver otra",
        )
    )


def extract_place_selection(text: str) -> int | None:
    normalized = _normalized(text)
    word_map = {
        "primera": 1,
        "primer": 1,
        "uno": 1,
        "esa": 1,
        "ese": 1,
        "me sirve": 1,
        "segunda": 2,
        "segundo": 2,
        "dos": 2,
        "tercera": 3,
        "tercero": 3,
        "tres": 3,
        "cuarta": 4,
        "cuarto": 4,
        "cuatro": 4,
    }
    for term, value in word_map.items():
        if term in normalized:
            return value
    match = re.search(r"\b(?:opcion|opción|centro|cda|cia|crc)?\s*#?\s*([1-9])\b", text or "", re.IGNORECASE)
    if match:
        return int(match.group(1))
    return None


def wants_quote(text: str) -> bool:
    lowered = (text or "").lower()
    terms = (
        "cotizar",
        "cotizacion",
        "cotización",
        "precio",
        "cuanto cuesta",
        "cuánto cuesta",
        "cuanto vale",
        "cuánto vale",
        "valor",
        "tarifa",
        "costo",
    )
    return wants_infraccion_quote(text) or any(term in lowered for term in terms)


def wants_payment(text: str) -> bool:
    lowered = (text or "").lower()
    return any(term in lowered for term in ("pagar", "pago", "factura", "recibo", "link de pago"))


def wants_handoff(text: str) -> bool:
    lowered = (text or "").lower()
    return any(term in lowered for term in ("asesor", "humano", "persona", "agente", "llameme", "llámeme"))


def wants_city_coverage(text: str) -> bool:
    normalized = _normalized(text)
    if not any(term in normalized for term in ("tecno", "tecnomecanica", "rtm", "cda")):
        return False
    coverage_terms = (
        "cobertura",
        "ciudad",
        "hay cda",
        "tienen cda",
        "atienden",
        "operan",
        "donde tienen",
    )
    return any(term in normalized for term in coverage_terms)


def wants_knowledge(text: str) -> bool:
    normalized = _normalized(text)
    if wants_quote(text) or wants_payment(text) or wants_handoff(text) or wants_cancel_appointment(text) or wants_reminder(text):
        return False
    if any(term in normalized for term in ("mis multas", "mis comparendos", "mi multa", "mi comparendo", "cuanto debo")):
        return False
    if wants_city_coverage(text):
        return True
    domain_terms = ("tecno", "tecnomecanica", "rtm", "cda", "cia", "curso", "comparendo", "fotomulta", "simit")
    question_terms = (
        "que revisan",
        "que llevar",
        "cada cuanto",
        "cuando toca",
        "cuanto dura",
        "duracion",
        "vigencia",
        "descargar",
        "descuento",
        "descuentos",
        "pasos",
        "marco legal",
        "que es simit",
        "sin descuento",
        "embriaguez",
        "vencida",
    )
    return any(term in normalized for term in domain_terms) and any(term in normalized for term in question_terms)


def knowledge_domain_for_text(text: str) -> str:
    normalized = _normalized(text)
    if any(term in normalized for term in ("tecno", "tecnomecanica", "rtm", "cda")):
        return "tecnomecanica"
    return "cia"


def knowledge_topic_for_text(text: str, *, domain: str | None = None) -> str:
    normalized = _normalized(text)
    selected_domain = domain or knowledge_domain_for_text(text)
    if selected_domain == "tecnomecanica":
        if "moto" in normalized:
            return "moto_especifico"
        if any(term in normalized for term in ("carro", "auto", "particular")):
            return "carro_especifico"
        if any(term in normalized for term in ("cada cuanto", "primera", "cuando toca", "frecuencia")):
            return "frecuencia"
        if any(term in normalized for term in ("multa", "vencida", "inmovil")):
            return "multa"
        if any(term in normalized for term in ("revisan", "inspeccionan", "chequean")):
            return "que_revisan"
        if any(term in normalized for term in ("llevar", "documento", "papeles")):
            return "que_llevar"
        if any(term in normalized for term in ("dura", "tiempo", "duracion")):
            return "duracion"
        if any(term in normalized for term in ("descargar", "runt")):
            return "como_descargar"
        if any(term in normalized for term in ("vigencia", "vence", "certificado")):
            return "vigencia"
        return "frecuencia"

    if "fotomulta" in normalized:
        return "descuentos_fotomulta"
    if any(term in normalized for term in (" en via", "agente", "transito")):
        return "descuentos_via"
    if "descuento" in normalized:
        return "descuentos"
    if any(term in normalized for term in ("paso", "hacer", "acceder")):
        return "pasos"
    if any(term in normalized for term in ("costo", "precio", "valor", "cuanto")):
        return "costo_curso"
    if any(term in normalized for term in ("desglose", "curso vs multa", "multa vs curso")):
        return "desglose_costos"
    if any(term in normalized for term in ("sin descuento", "embriaguez")):
        return "casos_sin_descuento"
    if "simit" in normalized:
        return "simit_link"
    if any(term in normalized for term in ("dura", "tiempo", "duracion")):
        return "duracion_curso"
    if any(term in normalized for term in ("llevar", "documento", "papeles")):
        return "que_llevar"
    if any(term in normalized for term in ("legal", "ley", "marco")):
        return "marco_legal"
    return "descuentos"


def quote_service_for_text(text: str) -> str:
    lowered = (text or "").lower()
    if wants_infraccion_quote(text):
        return "infraccion"
    if "curso" in lowered and any(term in lowered for term in ("multa", "comparendo", "cia")):
        return "curso_multa"
    if "soat" in lowered or "seguro" in lowered:
        return "soat"
    if wants_tecno(text):
        return "tecnomecanica"
    if "licencia" in lowered:
        return "licencia"
    if "mecanico" in lowered or "mecánico" in lowered:
        return "mecanico"
    return "servicio"


def extract_vehicle_type(text: str) -> str | None:
    lowered = (text or "").lower()
    for term in ("motocicleta", "moto", "taxi", "camioneta", "campero", "suv", "carro", "auto", "camion", "bus"):
        if term in lowered:
            return term
    return None


def extract_displacement(text: str) -> int | None:
    for match in DISPLACEMENT_RE.finditer(text or ""):
        value = int(match.group(1))
        if 50 <= value <= 9999 and not (1950 <= value <= 2039):
            return value
    return None


def extract_model_year(text: str) -> int | None:
    match = MODEL_RE.search(text or "")
    return int(match.group(1)) if match else None


def extract_infraction_code(text: str) -> str | None:
    match = INFRACTION_CODE_RE.search(text or "")
    return match.group(1).upper() if match else None


def extract_appointment_id(text: str) -> int | None:
    lowered = (text or "").lower()
    if not any(term in lowered for term in ("cita", "turno", "reserva")):
        return None
    for match in APPOINTMENT_ID_RE.finditer(text or ""):
        return int(match.group(1))
    return None


def extract_city(text: str) -> str | None:
    match = CITY_RE.search(text or "")
    if not match:
        return None
    city = match.group(1).lower()
    aliases = {
        "bogotá": "Bogota",
        "bogota": "Bogota",
        "bucaramanga": "Bucaramanga",
        "medellín": "Medellin",
        "medellin": "Medellin",
        "manizales": "Manizales",
        "cali": "Cali",
    }
    return aliases[city]


def extract_start_iso(text: str) -> str | None:
    match = ISO_DATE_RE.search(text or "")
    if not match:
        return None
    date = match.group(1)
    time = match.group(2) or "09:00"
    return f"{date}T{time}"


def procedure_for_text(text: str) -> str | None:
    if wants_tecno(text):
        return "tecnomecanica"
    lowered = (text or "").lower()
    if any(term in lowered for term in ("multa", "comparendo", "curso")):
        return "curso_multa"
    if "renov" in lowered:
        return "renovacion_licencia"
    if "licencia" in lowered:
        return "licencia_primera"
    return None


def _normalized(text: str) -> str:
    decomposed = unicodedata.normalize("NFKD", text or "")
    ascii_text = "".join(char for char in decomposed if not unicodedata.combining(char))
    return ascii_text.lower()
