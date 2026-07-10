from __future__ import annotations

import re
import unicodedata
from typing import Any

PLATE_RE = re.compile(r"\b([A-Z]{3}\s?\d{2}[A-Z0-9]|[A-Z]{3}\s?\d{3})\b", re.IGNORECASE)
DOCUMENT_RE = re.compile(
    r"(?:cedula|c[eé]dula|documento|cc|doc)\D{0,12}([0-9][0-9.\-\s]{3,18}[0-9])",
    re.IGNORECASE,
)
LOOSE_DOCUMENT_RE = re.compile(r"\b([0-9]{6,12})\b")
CITY_RE = re.compile(
    r"\b("
    r"bucaramanga|bogota|bogotá|medellin|medellín|manizales|cali|"
    r"barranquilla|pereira|cartagena|cucuta|cúcuta|ibague|ibagué|"
    r"santa\s*marta|villavicencio|popayan|popayán|palmira|zipaquira|zipaquirá|"
    r"itagui|itagüí|bello|sabaneta|soledad|monteria|montería"
    r")\b",
    re.IGNORECASE,
)
ISO_DATE_RE = re.compile(r"\b(20\d{2}-\d{2}-\d{2})(?:[ T](\d{2}:\d{2}))?\b")
DISPLACEMENT_RE = re.compile(r"\b([1-9][0-9]{1,3})\s*(?:cc|c\.c\.|cilindraje)?\b", re.IGNORECASE)
MODEL_RE = re.compile(r"\b(19[5-9][0-9]|20[0-3][0-9])\b")
INFRACTION_CODE_RE = re.compile(r"\b([A-I]\d{2})\b", re.IGNORECASE)
APPOINTMENT_ID_RE = re.compile(r"\b(?:cita|reserva|turno)?\s*#?\s*(\d{1,9})\b", re.IGNORECASE)
PARTNER_DECISION_RE = re.compile(
    r"\b(confirmar|rechazar)\s+#?\s*(\d{1,9})\b",
    re.IGNORECASE,
)


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
    if any(term in lowered for term in ("cotizar soat", "precio soat", "cuanto vale el soat", "cuánto vale el soat", "comprar soat")):
        return False
    value_terms = (
        "cuanto vale", "cuánto vale", "cuanto cuesta", "cuánto cuesta", "cuanto es",
        "qué cuesta", "que cuesta", "valor", "precio", "costo", "tarifa",
        "que multa", "qué multa", "que infraccion", "qué infracción", "que codigo", "qué código",
        "codigo de", "código de",
    )
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
        "espejo",
        "espejos",
        "chaleco",
        "gafas",
        "exosto",
        "exhosto",
        "escape",
        "ruido",
        "zona prohibida",
        "sitio restringido",
        "sin soat",
        "soat vencido",
    )
    personal_terms = ("mis multas", "mis comparendos", "mi multa", "mi comparendo", "cuanto debo", "cuánto debo")
    return (
        any(term in lowered for term in value_terms)
        and any(term in lowered for term in infraction_terms)
        and not any(term in lowered for term in personal_terms)
    )


def wants_infraccion_lookup(text: str) -> bool:
    """True when the user asks what a traffic fine/code is, not a Civi service quote."""
    if wants_infraccion_quote(text):
        return True
    if extract_infraction_code(text):
        return True
    lowered = _normalized(text)
    personal_terms = ("mis multas", "mis comparendos", "mi multa", "mi comparendo", "cuanto debo")
    if any(term in lowered for term in personal_terms):
        return False
    if any(term in lowered for term in ("cotizar soat", "precio soat", "comprar soat", "agendar", "cita")):
        return False
    # Strong conduct topics: enough alone to hit the catalog (no "cuanto vale" required).
    strong_topics = (
        "espejo", "espejos", "retrovisor",
        "exosto", "exhosto", "exsosto", "escape", "silenciador", "decibel",
        "me escape", "reten", "evadir control", "fuga de transito",
        "celular al volante", "usar celular",
        "chaleco", "reflectivo",
        "gafas", "lentes",
        "cinturon",
    )
    if any(term in lowered for term in strong_topics):
        return True
    # Weaker topics still need an explicit fine/value framing.
    weak_topics = (
        "semaforo", "luz roja", "pasarse el rojo",
        "pico y placa", "zona prohibida", "sitio restringido",
        "mal parqueo", "estacionar",
        "sin soat", "soat vencido",
    )
    question_terms = (
        "multa", "comparendo", "infraccion", "codigo",
        "cuanto", "vale", "cuesta", "sancion", "que pasa", "ilegal",
    )
    if any(term in lowered for term in weak_topics) and any(term in lowered for term in question_terms):
        return True
    return wants_infraccion_explanation(text)


def wants_infraccion_explanation(text: str) -> bool:
    lowered = (text or "").lower()
    if wants_infraccion_quote(text):
        return False
    explain_terms = (
        "que significa", "qué significa", "explicame", "explicación", "explicacion",
        "detalle de", "que es la multa", "en que consiste", "en qué consiste",
        "que infraccion es", "que codigo", "qué código",
        "por que me multaron", "por qué me multaron",
    )
    if not any(term in lowered for term in explain_terms):
        return False
    context_terms = (
        "multa", "comparendo", "infraccion", "infracción", "codigo", "código",
        "semaforo", "semáforo", "exosto", "escape", "espejo", "reten", "retén",
        "celular", "cinturon", "cinturón", "soat", "d0", "c0", "c2", "c3",
    )
    return any(term in lowered for term in context_terms)


def normalize_infraccion_query(text: str) -> str:
    """Fix common typos before catalog alias search."""
    lowered = (text or "").lower()
    replacements = (
        ("exsosto", "exosto"),
        ("exhosto", "exosto"),
        ("mmoficiado", "modificado"),
        ("moficiado", "modificado"),
        ("modoficado", "modificado"),
    )
    for old, new in replacements:
        lowered = lowered.replace(old, new)
    return lowered


def wants_general_multas_city(text: str) -> bool:
    lowered = _normalized(text)
    return any(
        term in lowered
        for term in (
            "general",
            "no se",
            "no se",
            "nacional",
            "da igual",
            "cualquiera",
            "en general",
            "mira general",
        )
    )


def wants_multas(text: str) -> bool:
    lowered = (text or "").lower()
    if wants_infraccion_quote(text):
        return False
    # Appointment procedure selection — not a SIMIT consult.
    if "curso" in lowered and any(term in lowered for term in ("multa", "comparendo")):
        personal = (
            "mis multas",
            "mis comparendos",
            "mi multa",
            "consultar multas",
            "ver multas",
            "mirar multas",
            "revisar multas",
        )
        if not any(term in lowered for term in personal):
            return False
    personal_or_consult = (
        "mis multas",
        "mis comparendos",
        "mi multa",
        "mi comparendo",
        "consultar multas",
        "ver multas",
        "mirar multas",
        "revisar multas",
        "buscar multas",
        "simit",
        "fotomulta",
        "fotomultas",
    )
    if any(term in lowered for term in personal_or_consult):
        return True
    # Broader: "multas" / "comparendos" as consult intent without "curso".
    if any(term in lowered for term in ("multas", "comparendos")):
        return True
    if "multa" in lowered or "comparendo" in lowered:
        action = ("consultar", "ver", "mirar", "revisar", "buscar", "tengo", "debo", "puedes")
        return any(term in lowered for term in action)
    return False


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


def extract_place_selection(text: str, *, places: list[dict[str, Any]] | None = None) -> int | None:
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

    if places:
        result = _match_place_by_text(text, places)
        if result is not None:
            return result

    return None


def _match_place_by_text(text: str, places: list[dict[str, Any]]) -> int | None:
    """Try to match user text against place names, cities, and kind abbreviations (1-indexed)."""
    lowered = (text or "").lower()
    if not lowered:
        return None

    for idx, place in enumerate(places, start=1):
        name = str(place.get("name", "")).lower()
        city = str(place.get("city", "")).lower()
        kind = str(place.get("kind", "")).upper()

        # Check if any word from user text appears in place name or city
        tokens = lowered.split()
        for token in tokens:
            if len(token) < 3:
                continue
            if token in name or token in city:
                return idx
            if token == kind.lower() or token in kind.lower():
                return idx

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
    lowered = _normalized(text)
    # "ASESORAME" alone is product advice, not human escalation.
    human_signals = (
        "asesor humano",
        "agente humano",
        "persona real",
        "persona humana",
        "hablar con alguien",
        "hablar con una persona",
        "pasar con un asesor",
        "pasame con un asesor",
        "quiero un asesor",
        "quiero hablar con un asesor",
        "llameme",
        "llamame",
    )
    return any(term in lowered for term in human_signals)


def wants_situational_advice(text: str) -> bool:
    lowered = (text or "").lower()
    hypothetical_markers = (
        "si me para", "si muestro", "si le muestro", "si demuestro",
        "me salvo", "me salvaria", "me salvara", "me libro",
        "me quitan", "me quitarian", "me quitaran", "me perdonan",
        "es legal", "es ilegal", "se puede", "puedo hacer",
        "me toca pagar", "me toca", "tengo que pagar",
        "que pasa si", "que pasaria si", "y si", "y si no",
        "hay excepcion", "hay alguna forma", "como me libro",
        "como hago para que no me multen", "como evitar",
        "que hago si", "si voy y", "si salgo y",
    )
    return any(term in lowered for term in hypothetical_markers)


def wants_general_traffic_question(text: str) -> bool:
    """Open-ended traffic Q&A that should use corpus search + LLM."""
    if wants_payment(text) or wants_quote(text) or wants_appointment(text) or wants_cancel_appointment(text):
        return False
    if wants_reminder(text) or wants_handoff(text):
        return False
    if wants_infraccion_lookup(text):
        return False
    if wants_situational_advice(text) or wants_accident_info(text) or wants_soat_info(text):
        return True

    lowered = (text or "").lower()
    question_shapes = (
        "puedo ", "puedo?", "es legal", "es ilegal", "que pasa", "qué pasa",
        "me multan", "me pueden multar", "me pueden parar", "que hago", "qué hago",
        "como hago", "cómo hago", "necesito saber", "explica", "explicame", "explícame",
        "en colombia", "segun la ley", "según la ley", "norma", "codigo de transito",
        "código de tránsito",
    )
    traffic_terms = (
        "transito", "tránsito", "comparendo", "multa", "infraccion", "infracción",
        "semaforo", "semáforo", "soat", "accidente", "choque", "licencia", "pico y placa",
        "parqueo", "velocidad", "cinturon", "cinturón", "celular", "moto", "carro",
        "agente", "policia", "policía", "via", "vía", "conductor",
    )
    return any(term in lowered for term in question_shapes) and any(term in lowered for term in traffic_terms)


def wants_soat_info(text: str) -> bool:
    lowered = (text or "").lower()
    terms = (
        "cubre", "cobertura", "cubrimiento", "cubrir", "reclamar al soat",
        "indemnizacion", "indemnización", "soat cubre", "que cubre el soat",
        "siniestro soat", "accidente soat", "reclamacion soat",
    )
    return any(term in lowered for term in terms)


def wants_accident_info(text: str) -> bool:
    lowered = (text or "").lower()
    terms = (
        "accidente", "choque", "chocar", "estrellon", "estrellar", "siniestro",
        "colision", "colisión", "golpe", "rayon", "rayón", "daño", "danos",
        "farola", "farol", "radiador", "parachoques", "capo", "puerta", "espejo",
        "vidrio", "llanta", "faro",
        "me chocaron", "me estrellaron", "choque simple",
    )
    return any(term in lowered for term in terms)


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
    if wants_accident_info(text) and not wants_quote(text) and not wants_vigencia(text):
        return True
    if wants_soat_info(text) and not wants_quote(text) and not wants_vigencia(text):
        return True
    if wants_city_coverage(text):
        return True
    domain_terms = (
        "tecno", "tecnomecanica", "rtm", "cda", "cia", "curso", "comparendo",
        "fotomulta", "simit", "soat", "seguro", "accidente", "choque", "siniestro",
        "colision", "farola", "infraccion", "cubre", "cobertura",
    )
    question_terms = (
        "que revisan", "que llevar", "cada cuanto", "cuando toca",
        "cuanto dura", "duracion", "vigencia", "descargar", "descuento",
        "descuentos", "pasos", "marco legal", "que es simit", "sin descuento",
        "embriaguez", "vencida", "explicame", "explicación", "significa",
        "cubre", "cobertura", "pasos", "hacer en caso",
    )
    return any(term in normalized for term in domain_terms) and any(term in normalized for term in question_terms)


def knowledge_domain_for_text(text: str) -> str:
    normalized = _normalized(text)
    if any(term in normalized for term in ("tecno", "tecnomecanica", "rtm", "cda")) and not wants_soat_info(text) and not wants_accident_info(text):
        return "tecnomecanica"
    if any(term in normalized for term in ("soat", "seguro", "cubre", "cobertura")) or wants_soat_info(text):
        return "soat"
    if any(term in normalized for term in ("accidente", "choque", "siniestro", "colision", "estrellon", "daños", "danos", "chocar", "golpe")) or wants_accident_info(text):
        return "accidente"
    if any(term in normalized for term in ("infraccion", "infracciones", "codigo", "leer multa", "comparendo", "fotomulta", "multa")) and not wants_quote(text):
        return "infracciones"
    return "cia"


def knowledge_topic_for_text(text: str, *, domain: str | None = None) -> str:
    normalized = _normalized(text)
    selected_domain = domain or knowledge_domain_for_text(text)

    if selected_domain == "soat":
        if any(term in normalized for term in ("cubre", "cobertura", "cubrimiento", "que incluye")):
            return "que_cubre"
        if any(term in normalized for term in ("accidente", "choque", "pasos", "que hacer", "reclamar")):
            return "en_accidente"
        if any(term in normalized for term in ("cuanto cubre", "montos", "valor soat", "cuanto paga")):
            return "cuanto_cubre"
        if any(term in normalized for term in ("sin soat", "no tengo soat", "multa soat", "vencido", "consecuencia")):
            return "sin_soat"
        if any(term in normalized for term in ("emergencia", "numero", "telefono", "llamar", "contacto")):
            return "contacto_emergencia"
        return "que_cubre"

    if selected_domain == "accidente":
        if any(term in normalized for term in ("herido", "lesion", "lesionado", "sangre", "ambulancia")):
            return "heridos"
        if any(term in normalized for term in ("documento", "papel", "que necesito", "llevar")):
            return "documentos_necesarios"
        if any(term in normalized for term in ("paga", "pagas", "responsable", "culpa", "responsabilidad", "quien cubre")):
            return "responsabilidad"
        return "checklist"

    if selected_domain == "infracciones":
        if any(term in normalized for term in ("categoria", "categorias", "valores", "cuanto vale la multa")):
            return "categorias"
        if any(term in normalized for term in ("leer", "comparendo", "como entender", "como se lee")):
            return "leer_multa"
        if any(term in normalized for term in ("luz", "farola", "farol", "faro", "luces", "bombillo")):
            return "luces"
        if any(term in normalized for term in ("cinturon", "cinturón")):
            return "cinturon"
        if any(term in normalized for term in ("embriaguez", "alcohol", "borracho", "trago", "grado")):
            return "embriaguez"
        if any(term in normalized for term in ("estacionar", "parqueo", "parquear", "aparcar", "mal parqueado")):
            return "estacionamiento"
        if any(term in normalized for term in ("celular", "telefono", "teléfono", "manipular")):
            return "celular"
        if any(term in normalized for term in ("semaforo", "semáforo", "luz roja", "pasarse el rojo", "cruzar en rojo")):
            return "semaforo"
        if any(term in normalized for term in ("espejo", "espejos", "retrovisor", "retrovisores")):
            return "espejos"
        if any(term in normalized for term in ("pico y placa", "zona prohibida", "sitio restringido", "restringida")):
            return "zona_restringida"
        if any(term in normalized for term in ("chaleco", "reflectivo", "kit carretera", "triangulo", "triángulo")):
            return "chaleco"
        if any(term in normalized for term in ("gafas", "lentes", "anteojos")):
            return "gafas"
        if any(term in normalized for term in ("exosto", "exhosto", "escape", "ruido", "decibel", "antirruido")):
            return "ruido"
        if any(term in normalized for term in ("velocidad", "rapido", "exceso", "km")):
            return "velocidad"
        if any(term in normalized for term in ("varado", "grua", "grúa", "averiado", "no enciende", "apagado")):
            return "varado"
        if any(term in normalized for term in ("soat", "seguro")):
            return "soat_falta"
        return "categorias"

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

    if selected_domain == "cia":
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


def extract_partner_decision(text: str) -> tuple[str, int] | None:
    match = PARTNER_DECISION_RE.search(text or "")
    if not match:
        return None
    action = match.group(1).lower()
    return action, int(match.group(2))


def extract_city(text: str) -> str | None:
    match = CITY_RE.search(text or "")
    if not match:
        return None
    city = re.sub(r"\s+", " ", match.group(1).lower()).strip()
    aliases = {
        "bogotá": "Bogota",
        "bogota": "Bogota",
        "bucaramanga": "Bucaramanga",
        "medellín": "Medellin",
        "medellin": "Medellin",
        "manizales": "Manizales",
        "cali": "Cali",
        "barranquilla": "Barranquilla",
        "pereira": "Pereira",
        "cartagena": "Cartagena",
        "cucuta": "Cucuta",
        "cúcuta": "Cucuta",
        "ibague": "Ibague",
        "ibagué": "Ibague",
        "santa marta": "Santa Marta",
        "villavicencio": "Villavicencio",
        "popayan": "Popayan",
        "popayán": "Popayan",
        "palmira": "Palmira",
        "zipaquira": "Zipaquira",
        "zipaquirá": "Zipaquira",
        "itagui": "Itagui",
        "itagüí": "Itagui",
        "bello": "Bello",
        "sabaneta": "Sabaneta",
        "soledad": "Soledad",
        "monteria": "Monteria",
        "montería": "Monteria",
    }
    return aliases.get(city)


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


def mentions_crc(text: str) -> bool:
    return "crc" in _normalized(text)


def _normalized(text: str) -> str:
    decomposed = unicodedata.normalize("NFKD", text or "")
    ascii_text = "".join(char for char in decomposed if not unicodedata.combining(char))
    return ascii_text.lower()
