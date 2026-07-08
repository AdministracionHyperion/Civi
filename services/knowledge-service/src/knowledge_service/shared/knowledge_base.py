from __future__ import annotations

from dataclasses import dataclass
import unicodedata


@dataclass(frozen=True)
class KnowledgeItem:
    topic: str
    title: str
    body: str


TECNOMECANICA_INFO: dict[str, KnowledgeItem] = {
    "frecuencia": KnowledgeItem(
        topic="frecuencia",
        title="Cada cuanto se hace la tecnomecanica",
        body=(
            "Para carros particulares la primera revision se hace 6 anos despues de la matricula y luego se renueva "
            "cada ano. Para motos y vehiculos de servicio publico, la primera es a los 2 anos y tambien se renueva "
            "cada ano."
        ),
    ),
    "multa": KnowledgeItem(
        topic="multa",
        title="Multa por tecnomecanica vencida",
        body=(
            "Circular con tecnomecanica vencida puede generar multa de 15 salarios minimos diarios legales vigentes "
            "e inmovilizacion del vehiculo. El valor exacto y descuentos se validan con la autoridad o SIMIT."
        ),
    ),
    "que_revisan": KnowledgeItem(
        topic="que_revisan",
        title="Que revisan en la tecnomecanica",
        body=(
            "Revisan frenos, direccion, luces, senales, llantas, suspension, carroceria, vidrios, sistema de escape "
            "y emisiones. En motos tambien revisan cadena, retrovisores y elementos propios de la moto."
        ),
    ),
    "que_llevar": KnowledgeItem(
        topic="que_llevar",
        title="Que llevar a la tecnomecanica",
        body=(
            "Lleva cedula, tarjeta de propiedad y SOAT vigente. Tambien conviene revisar luces, llantas, frenos y "
            "elementos de seguridad antes de ir al CDA."
        ),
    ),
    "duracion": KnowledgeItem(
        topic="duracion",
        title="Duracion de la revision",
        body=(
            "La revision suele tomar entre 30 y 60 minutos para carros y motos particulares. Vehiculos pesados o de "
            "servicio publico pueden tardar mas."
        ),
    ),
    "vigencia": KnowledgeItem(
        topic="vigencia",
        title="Vigencia del certificado",
        body=(
            "El certificado de tecnomecanica dura 1 ano desde la fecha de aprobacion. Lo prudente es agendar la "
            "renovacion antes del vencimiento."
        ),
    ),
    "como_descargar": KnowledgeItem(
        topic="como_descargar",
        title="Como descargar el certificado",
        body=(
            "El certificado queda registrado en RUNT. Puedes consultarlo en el portal ciudadano del RUNT con placa "
            "y datos del titular; el CDA tambien puede entregarte copia."
        ),
    ),
    "moto_especifico": KnowledgeItem(
        topic="moto_especifico",
        title="Tecnomecanica para motos",
        body=(
            "En motos la primera revision es a los 2 anos de la matricula y luego anual. Antes de ir revisa luces, "
            "direccionales, frenos, cadena, llantas, pito, espejos y escape."
        ),
    ),
    "carro_especifico": KnowledgeItem(
        topic="carro_especifico",
        title="Tecnomecanica para carros particulares",
        body=(
            "En carros particulares la primera revision es a los 6 anos de la matricula y luego anual. Revisa luces, "
            "llantas, frenos, limpiabrisas, cinturones, emisiones y equipo de carretera antes de ir."
        ),
    ),
}


CIA_INFO: dict[str, KnowledgeItem] = {
    "descuentos": KnowledgeItem(
        topic="descuentos",
        title="Descuentos por curso pedagogico",
        body=(
            "Los descuentos dependen de si el comparendo fue impuesto en via o por fotomulta. Primero confirma el "
            "origen del comparendo y los dias habiles desde la imposicion o notificacion."
        ),
    ),
    "descuentos_via": KnowledgeItem(
        topic="descuentos_via",
        title="Descuentos para comparendo en via",
        body=(
            "Para comparendo impuesto en via, normalmente hay 50% si pagas y haces curso dentro de 5 dias habiles; "
            "25% entre el dia 6 y 20 habil. Despues suele perderse el descuento."
        ),
    ),
    "descuentos_fotomulta": KnowledgeItem(
        topic="descuentos_fotomulta",
        title="Descuentos para fotomulta",
        body=(
            "Para fotomulta, normalmente hay 50% si pagas y haces curso dentro de 11 dias habiles desde la "
            "notificacion; 25% entre el dia 12 y 26 habil. La autoridad debe confirmar el caso."
        ),
    ),
    "pasos": KnowledgeItem(
        topic="pasos",
        title="Pasos para acceder al descuento",
        body=(
            "Los pasos son: consultar el comparendo, agendar curso en un CIA autorizado, asistir al curso pedagogico "
            "y pagar con el descuento que corresponda cuando la autoridad lo liquide."
        ),
    ),
    "costo_curso": KnowledgeItem(
        topic="costo_curso",
        title="Valor referencial del curso",
        body=(
            "El curso CIA es un costo separado del valor de la multa. El valor final lo confirma el aliado al "
            "agendar, porque puede variar por ciudad y liquidacion."
        ),
    ),
    "desglose_costos": KnowledgeItem(
        topic="desglose_costos",
        title="Multa, curso y descuento",
        body=(
            "Son tres conceptos distintos: la multa depende de la infraccion, el curso se paga al CIA, y el "
            "descuento aplica sobre la multa cuando cumples los plazos y requisitos."
        ),
    ),
    "casos_sin_descuento": KnowledgeItem(
        topic="casos_sin_descuento",
        title="Casos que pueden no tener descuento",
        body=(
            "Infracciones graves como embriaguez o algunas categorias especiales pueden no admitir descuento por "
            "curso. El SIMIT o la autoridad local deben confirmar el estado real."
        ),
    ),
    "simit_link": KnowledgeItem(
        topic="simit_link",
        title="Consulta oficial de comparendos",
        body=(
            "SIMIT es la fuente nacional para consultar comparendos y multas. Para consultar tu caso necesito tu "
            "documento, y el bot lo valida por la ruta SIMIT configurada."
        ),
    ),
    "duracion_curso": KnowledgeItem(
        topic="duracion_curso",
        title="Duracion del curso pedagogico",
        body="El curso pedagogico suele durar alrededor de 2 horas y se realiza en un CIA autorizado.",
    ),
    "que_llevar": KnowledgeItem(
        topic="que_llevar",
        title="Que llevar al curso",
        body="Lleva cedula y, si lo tienes, numero del comparendo o soporte del estado de cuenta. No necesitas llevar el vehiculo.",
    ),
    "marco_legal": KnowledgeItem(
        topic="marco_legal",
        title="Marco legal",
        body=(
            "La base general esta en el Codigo Nacional de Transito. La aplicacion exacta depende de la autoridad, "
            "el tipo de comparendo y los plazos."
        ),
    ),
}


DOMAIN_ITEMS = {
    "tecnomecanica": TECNOMECANICA_INFO,
    "cia": CIA_INFO,
}

DOMAIN_ALIASES = {
    "tecno": "tecnomecanica",
    "tecnomecanica": "tecnomecanica",
    "tecnomecanica": "tecnomecanica",
    "rtm": "tecnomecanica",
    "cda": "tecnomecanica",
    "curso": "cia",
    "curso_multa": "cia",
    "multa": "cia",
    "comparendo": "cia",
    "fotomulta": "cia",
    "cia": "cia",
}


CITY_COVERAGE = {
    "bucaramanga": {
        "city": "Bucaramanga",
        "service_type": "tecnomecanica",
        "enabled": True,
        "total_places": 1,
        "total_partners": 1,
        "notes": (
            "En Bucaramanga hay cobertura operativa cargada para tecnomecanica y un CDA aliado en el catalogo local "
            "de Civi. Para agendar, el bot puede buscar el centro mas cercano."
        ),
    },
    "bogota": {
        "city": "Bogota",
        "service_type": "tecnomecanica",
        "enabled": True,
        "total_places": 1,
        "total_partners": 0,
        "notes": (
            "En Bogota hay cobertura logica para tecnomecanica y un CDA cargado en catalogo, sin aliado marcado en "
            "este entorno. Las reglas de pico y placa cambian; confirma en fuentes oficiales antes de moverte."
        ),
    },
}


def normalize_key(value: str) -> str:
    stripped = unicodedata.normalize("NFKD", value or "")
    ascii_value = "".join(char for char in stripped if not unicodedata.combining(char))
    return ascii_value.strip().lower().replace("-", "_").replace(" ", "_")


def normalize_domain(value: str) -> str | None:
    return DOMAIN_ALIASES.get(normalize_key(value))


def available_topics(domain: str) -> list[str]:
    items = DOMAIN_ITEMS.get(domain) or {}
    return sorted(items)


def get_item(domain: str, topic: str) -> KnowledgeItem | None:
    items = DOMAIN_ITEMS.get(domain) or {}
    return items.get(normalize_key(topic))


def get_city_coverage(city: str) -> dict[str, object]:
    normalized = normalize_key(city)
    if normalized in CITY_COVERAGE:
        return dict(CITY_COVERAGE[normalized])
    enabled_cities = [str(item["city"]) for item in CITY_COVERAGE.values()]
    return {
        "city": city.strip().title() if city else "",
        "service_type": "tecnomecanica",
        "enabled": False,
        "total_places": 0,
        "total_partners": 0,
        "notes": "",
        "nearby_cities": enabled_cities,
    }
