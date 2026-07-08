from __future__ import annotations

import re
import unicodedata
from datetime import date
from typing import Any


SERVICE_PUBLIC_CLASSES = (
    "BUS",
    "BUSETA",
    "CAMION",
    "CAMIONETA DE SERVICIO PUBLICO",
    "MICROBUS",
    "TAXI",
    "TRANSPORTE DE CARGA",
    "VOLQUETA",
)
ELECTRIC_HYBRID_CLASSES = ("ELECTRICO", "HIBRIDO")


def build_vehicle_payload(
    *,
    placa: str,
    info_general: dict[str, Any],
    soat_data: dict[str, Any] | None,
    rtm_data: dict[str, Any] | None,
    multas: dict[str, Any] | None = None,
    today: date | None = None,
) -> dict[str, Any]:
    active_today = today or date.today()
    soat_analysis = analyze_soat(soat_data or {}, today=active_today)
    rtm_analysis = analyze_rtm(
        fecha_matricula=info_general.get("fechaMatricula"),
        clase_vehiculo=info_general.get("claseVehiculo"),
        tiene_rtm_vigente=bool((rtm_data or {}).get("tieneRTMVigente")),
        fecha_vencimiento=(rtm_data or {}).get("fechaVencimiento"),
        today=active_today,
    )

    result = {
        "success": True,
        "placa": placa.strip().upper(),
        "fromCache": False,
        "vehiculo": {
            "placa": placa.strip().upper(),
            "fechaMatricula": info_general.get("fechaMatricula"),
            "claseVehiculo": info_general.get("claseVehiculo"),
            "marca": info_general.get("marca"),
            "modelo": info_general.get("modelo"),
            "linea": info_general.get("linea"),
            "color": info_general.get("color"),
            "cilindraje": info_general.get("cilindraje"),
            "estado": info_general.get("estado"),
            "tipoServicio": info_general.get("tipoServicio"),
        },
        "soat": {
            "fechaVencimiento": (soat_data or {}).get("fechaVencimiento"),
            "aseguradora": (soat_data or {}).get("aseguradora"),
            "poliza": (soat_data or {}).get("poliza"),
            "estado": (soat_data or {}).get("estado"),
            **soat_analysis,
        },
        "rtm": {
            "tieneRTMVigente": bool((rtm_data or {}).get("tieneRTMVigente")),
            **rtm_analysis,
        },
        "multas": multas,
        "alertas": [],
    }

    if not result["soat"]["vigente"]:
        result["alertas"].append(
            {"tipo": "SOAT", "nivel": "CRITICO", "mensaje": result["soat"]["advertencia"] or "SOAT no vigente"}
        )
    elif result["soat"]["advertencia"]:
        result["alertas"].append({"tipo": "SOAT", "nivel": "ADVERTENCIA", "mensaje": result["soat"]["advertencia"]})

    if result["rtm"]["debePagarRTM"]:
        result["alertas"].append({"tipo": "RTM", "nivel": "CRITICO", "mensaje": result["rtm"]["motivo"]})
    elif result["rtm"]["advertencia"]:
        result["alertas"].append({"tipo": "RTM", "nivel": "INFO", "mensaje": result["rtm"]["advertencia"]})

    if multas and multas.get("tieneMultas"):
        resumen = multas.get("resumen") or {}
        result["alertas"].append(
            {
                "tipo": "SIMIT",
                "nivel": "CRITICO",
                "mensaje": (
                    f"Presenta multas en SIMIT. Total: $ {resumen.get('total', 0)} "
                    f"(Comparendos: {resumen.get('comparendos', 0)}, Multas: {resumen.get('multas', 0)})"
                ),
            }
        )

    return result


def analyze_soat(soat_data: dict[str, Any], *, today: date | None = None) -> dict[str, Any]:
    result: dict[str, Any] = {"vigente": False, "diasRestantes": None, "advertencia": None}
    fecha_vencimiento = parse_date(str(soat_data.get("fechaVencimiento") or ""))
    if fecha_vencimiento is None:
        result["advertencia"] = "No se encontro informacion del SOAT."
        return result

    active_today = today or date.today()
    days = (fecha_vencimiento - active_today).days
    estado = str(soat_data.get("estado") or "").strip().upper()
    result["diasRestantes"] = days
    result["vigente"] = estado == "VIGENTE" and days > 0

    if not result["vigente"]:
        result["advertencia"] = f"SOAT VENCIDO. Vencio el {soat_data.get('fechaVencimiento')}."
    elif days <= 30:
        result["advertencia"] = f"SOAT proximo a vencer en {days} dias."
    return result


def analyze_rtm(
    *,
    fecha_matricula: Any,
    clase_vehiculo: Any,
    tiene_rtm_vigente: bool,
    fecha_vencimiento: Any = None,
    today: date | None = None,
) -> dict[str, Any]:
    result: dict[str, Any] = {
        "debePagarRTM": False,
        "motivo": "",
        "proximaFechaRTM": None,
        "diasRestantes": None,
        "advertencia": None,
    }
    active_today = today or date.today()

    if tiene_rtm_vigente:
        result["motivo"] = "Tiene certificado RTM vigente. No requiere pago inmediato."
        result["proximaFechaRTM"] = fecha_vencimiento
        parsed_due_date = parse_date(str(fecha_vencimiento or ""))
        if parsed_due_date is not None:
            days = (parsed_due_date - active_today).days
            result["diasRestantes"] = days
            if days <= 30:
                result["advertencia"] = f"RTM proximo a vencer en {days} dias."
        return result

    parsed_registration = parse_date(str(fecha_matricula or ""))
    if parsed_registration is None:
        result["advertencia"] = "No se pudo determinar la fecha de matricula."
        return result

    grace_years = grace_years_for_vehicle_class(str(clase_vehiculo or ""))
    if grace_years is None:
        result["advertencia"] = (
            f"El vehiculo ({clase_vehiculo}) requiere revision especial segun normativa CDA."
        )
        return result

    first_rtm_date = add_years(parsed_registration, grace_years)
    if active_today < first_rtm_date:
        days = (first_rtm_date - active_today).days
        result["proximaFechaRTM"] = format_date(first_rtm_date)
        result["diasRestantes"] = days
        result["motivo"] = (
            f"Primera RTM a los {grace_years} anos de matricula. "
            f"Faltan {days} dias ({result['proximaFechaRTM']})."
        )
        return result

    result["debePagarRTM"] = True
    result["motivo"] = (
        f"El vehiculo requiere RTM. Primera cita fue el {format_date(first_rtm_date)} "
        "y no tiene certificado vigente."
    )
    return result


def grace_years_for_vehicle_class(vehicle_class: str) -> int | None:
    normalized = fold(vehicle_class)
    if normalized == "MOTOCICLETA":
        return 2
    if any(item in normalized for item in SERVICE_PUBLIC_CLASSES):
        return 2
    if any(item in normalized for item in ELECTRIC_HYBRID_CLASSES):
        return None
    return 5


def parse_date(value: str) -> date | None:
    match = re.search(r"\b(\d{2})/(\d{2})/(\d{4})\b", value)
    if not match:
        return None
    day, month, year = (int(part) for part in match.groups())
    try:
        return date(year, month, day)
    except ValueError:
        return None


def add_years(value: date, years: int) -> date:
    try:
        return value.replace(year=value.year + years)
    except ValueError:
        return value.replace(month=2, day=28, year=value.year + years)


def format_date(value: date) -> str:
    return value.strftime("%d/%m/%Y")


def fold(value: str) -> str:
    without_accents = unicodedata.normalize("NFKD", value).encode("ascii", "ignore").decode("ascii")
    return re.sub(r"\s+", " ", without_accents).strip().upper()
