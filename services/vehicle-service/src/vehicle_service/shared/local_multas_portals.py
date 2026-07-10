from __future__ import annotations

import re
import unicodedata


PORTAL_URLS: dict[str, str] = {
    "Bogota": "https://webfenix.movilidadbogota.gov.co/#/consulta-pagos",
    "Medellin": "https://www.medellin.gov.co/es/secretaria-de-movilidad/",
    "Barranquilla": "https://barranquilla.gov.co/transito",
    "Bucaramanga": "https://transitobucaramanga.gov.co/dtb/atencion-y-servicios-a-la-ciudadania/tramites-virtuales-portal",
    "Pereira": "https://www.movilidadpereira.gov.co/",
    "Manizales": "https://www.movilidadmanizales.com.co/portal-servicios/",
    "Cali": "https://www.cali.gov.co/movilidad/",
    "Cartagena": "https://www.fcm.org.co/simit",
    "Cucuta": "https://www.fcm.org.co/simit",
    "Ibague": "https://www.fcm.org.co/simit",
    "Santa Marta": "https://www.fcm.org.co/simit",
    "Villavicencio": "https://www.fcm.org.co/simit",
    "Popayan": "https://www.fcm.org.co/simit",
    "Palmira": "https://www.fcm.org.co/simit",
    "Zipaquira": "https://www.fcm.org.co/simit",
    "Itagui": "https://www.transitoitagui.gov.co/",
    "Bello": "https://www.fcm.org.co/simit",
    "Sabaneta": "https://www.fcm.org.co/simit",
    "Soledad": "https://www.fcm.org.co/simit",
    "Monteria": "https://www.fcm.org.co/simit",
}


def normalize_city(value: str | None) -> str | None:
    if not value:
        return None
    folded = unicodedata.normalize("NFKD", value)
    ascii_text = "".join(char for char in folded if not unicodedata.combining(char))
    key = re.sub(r"\s+", " ", ascii_text.strip().lower())
    aliases = {
        "bogota": "Bogota",
        "medellin": "Medellin",
        "barranquilla": "Barranquilla",
        "bucaramanga": "Bucaramanga",
        "pereira": "Pereira",
        "manizales": "Manizales",
        "cali": "Cali",
        "cartagena": "Cartagena",
        "cucuta": "Cucuta",
        "ibague": "Ibague",
        "santa marta": "Santa Marta",
        "villavicencio": "Villavicencio",
        "popayan": "Popayan",
        "palmira": "Palmira",
        "zipaquira": "Zipaquira",
        "itagui": "Itagui",
        "bello": "Bello",
        "sabaneta": "Sabaneta",
        "soledad": "Soledad",
        "monteria": "Monteria",
    }
    return aliases.get(key)


def portal_url_for_city(ciudad: str | None) -> str | None:
    normalized = normalize_city(ciudad)
    if not normalized:
        return None
    return PORTAL_URLS.get(normalized)


def supports_live_local_consult(ciudad: str | None) -> bool:
    return normalize_city(ciudad) == "Manizales"
