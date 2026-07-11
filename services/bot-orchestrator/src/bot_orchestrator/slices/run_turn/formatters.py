from __future__ import annotations

import re
from typing import Any


ISO_DATE_RE = re.compile(r"^(\d{4})-(\d{2})-(\d{2})$")
DDMMYYYY_RE = re.compile(r"^(\d{2})/(\d{2})/(\d{4})$")

TIPO_LABELS: dict[str, str] = {
    "CDA": "CDA (revision tecnico-mecanica)",
    "CRC": "CRC (renovacion de licencia)",
    "CEA": "CEA (curso de conduccion)",
    "CIA": "CIA (curso pedagogico por multa)",
}

DATE_EXAMPLES = "*manana a las 10*, *el jueves 3pm* o *2026-07-10 09:00*"

VEHICLE_PLATE_EXAMPLE = "ABC123"
VEHICLE_DOCUMENT_EXAMPLE = "1234567890"


def format_vehicle_slots_request(*, need_placa: bool, need_documento: bool) -> str:
    """Standard ask for placa/cedula when starting or resuming a RUNT vigencia consult."""
    if need_placa and need_documento:
        what = "la *placa* y *cedula*"
        example = f"{VEHICLE_PLATE_EXAMPLE} {VEHICLE_DOCUMENT_EXAMPLE}"
    elif need_placa:
        what = "la *placa*"
        example = VEHICLE_PLATE_EXAMPLE
    elif need_documento:
        what = "la *cedula*"
        example = VEHICLE_DOCUMENT_EXAMPLE
    else:
        raise ValueError("format_vehicle_slots_request requires at least one missing slot")
    return (
        f"Claro, con gusto. Pasame {what} como el siguiente ejemplo por favor "
        f"{example} 😊"
    )


def format_multas_city_request() -> str:
    return (
        "Claro, con gusto. ¿En qué ciudad crees que te pusieron la multa? "
        "Si no sabes, dime *nacional* o *no sé* 😊"
    )


def format_multas_query_request(*, ciudad: str | None = None) -> str:
    example = f"{VEHICLE_PLATE_EXAMPLE} o {VEHICLE_DOCUMENT_EXAMPLE}"
    if ciudad:
        return (
            f"Claro, con gusto. Para consultar en *{ciudad}*, pasame la *placa* o la *cedula* "
            f"como el siguiente ejemplo por favor {example} 😊"
        )
    return (
        "Claro, con gusto. Pasame la *placa* o la *cedula* "
        f"como el siguiente ejemplo por favor {example} 😊"
    )


def _format_ddmmyyyy(value: object) -> str | None:
    if not isinstance(value, str):
        return None
    text = value.strip()
    if not text:
        return None
    iso_match = ISO_DATE_RE.match(text)
    if iso_match:
        year, month, day = iso_match.groups()
        return f"{day}/{month}/{year}"
    if DDMMYYYY_RE.match(text):
        return text
    return text


def _vehicle_descriptor(data: dict[str, Any]) -> str:
    vehiculo = data.get("vehiculo") or {}
    marca = str(vehiculo.get("marca") or "").strip()
    linea = str(vehiculo.get("linea") or "").strip()
    modelo = vehiculo.get("modelo")
    clase = str(vehiculo.get("claseVehiculo") or "").strip().lower()
    color = str(vehiculo.get("color") or "").strip().lower()
    placa = str(data.get("placa") or vehiculo.get("placa") or "").strip().upper()

    parts: list[str] = []
    name = " ".join(bit for bit in (marca, linea) if bit)
    if name:
        parts.append(f"*{name}*")
    detail = " ".join(bit for bit in (clase, color) if bit)
    if detail:
        parts.append(f"({detail})")
    if modelo:
        parts.append(f"modelo {modelo}")
    if placa:
        parts.append(f"placa *{placa}*")
    if parts:
        return ", ".join(parts)
    if placa:
        return f"vehiculo placa *{placa}*"
    return "tu vehiculo"


def _vehicle_label(data: dict[str, Any]) -> str:
    vehicle = data.get("vehiculo") or {}
    parts = [
        vehicle.get("marca"),
        vehicle.get("linea"),
        str(vehicle.get("modelo")) if vehicle.get("modelo") else None,
    ]
    label = " ".join(str(part).strip() for part in parts if part)
    placa = data.get("placa") or vehicle.get("placa")
    if label and placa:
        return f"{label} {placa}"
    if placa:
        return f"vehiculo {placa}"
    return "vehiculo"


def _quote_summary(quote: dict[str, Any] | None) -> str | None:
    if not quote:
        return None
    message = quote.get("message")
    if isinstance(message, str) and message.strip():
        return message.strip()
    price = quote.get("price_cop")
    if isinstance(price, int) and price > 0:
        return f"{price:,.0f} COP".replace(",", ".")
    return None


def format_vigencia_response(
    data: dict[str, Any],
    *,
    intent: str,
    quote: dict[str, Any] | None = None,
) -> str:
    if intent == "soat":
        return _format_soat_response(data, quote=quote)
    return _format_tecno_response(data, quote=quote)


def _format_soat_response(data: dict[str, Any], *, quote: dict[str, Any] | None) -> str:
    soat = data.get("soat") or {}
    descriptor = _vehicle_descriptor(data)
    fecha = _format_ddmmyyyy(soat.get("fechaVencimiento"))
    dias = soat.get("diasRestantes")
    vigente = bool(soat.get("vigente", True))

    if not fecha:
        return "No me llego una fecha clara del SOAT. Pasame placa y cedula del titular para consultar de nuevo."

    parts = [f"Listo. Tu {descriptor}"]
    if not vigente:
        parts.append(f"tiene el SOAT *vencido* (fecha registrada: *{fecha}*).")
    elif isinstance(dias, int):
        parts.append(f"tiene SOAT vigente hasta el *{fecha}* (faltan {dias} dias).")
    else:
        parts.append(f"tiene SOAT vigente hasta el *{fecha}*.")

    quote_msg = _quote_summary(quote)
    if quote_msg:
        parts.append(f"Referencia: *{quote_msg}*.")

    if soat_needs_quote(data):
        parts.append("Quieres que te ayude con la renovacion del SOAT?")
    return " ".join(parts)


def _format_tecno_response(data: dict[str, Any], *, quote: dict[str, Any] | None) -> str:
    rtm = data.get("rtm") or {}
    descriptor = _vehicle_descriptor(data)
    label = _vehicle_label(data)
    fecha = _format_ddmmyyyy(rtm.get("proximaFechaRTM") or rtm.get("fechaVencimiento"))
    dias = rtm.get("diasRestantes")
    debe_pagar = bool(rtm.get("debePagarRTM"))
    vigente = bool(rtm.get("tieneRTMVigente"))
    motivo = str(rtm.get("motivo") or "").strip()

    if not fecha and not motivo:
        return (
            "No me llego una fecha clara de la tecnomecanica. "
            "Pasame placa y cedula del titular para consultar de nuevo."
        )

    parts = [f"Listo. Tu {descriptor}"]
    if debe_pagar:
        if fecha:
            parts.append(
                f"tiene la tecnomecanica *vencida*. La fecha registrada era *{fecha}*."
            )
        else:
            parts.append("tiene la tecnomecanica *vencida*.")
    elif vigente and fecha:
        if isinstance(dias, int):
            parts.append(f"tiene tecnomecanica vigente hasta el *{fecha}* (faltan {dias} dias).")
        else:
            parts.append(f"tiene tecnomecanica vigente hasta el *{fecha}*.")
    elif fecha:
        if _is_first_review_motivo(motivo):
            if isinstance(dias, int):
                parts.append(
                    f"tiene primera revision tecnico-mecanica obligatoria para el *{fecha}* "
                    f"(faltan {dias} dias)."
                )
            else:
                parts.append(f"tiene primera revision tecnico-mecanica obligatoria para el *{fecha}*.")
            parts.append("Como esta recien matriculado, aun no necesitas hacerla.")
        else:
            parts.append(f"tiene tecnomecanica hasta el *{fecha}*.")
    else:
        parts.append(motivo or f"aun no tengo fecha clara para {label}.")

    quote_msg = _quote_summary(quote)
    if quote_msg:
        parts.append(f"Referencia: *{quote_msg}*.")

    if tecno_needs_quote(data):
        parts.append("Quieres que te ayude a agendar la cita?")
    return " ".join(parts)


def _is_first_review_motivo(motivo: str) -> bool:
    lowered = motivo.lower()
    return "primera" in lowered or "recien" in lowered or "recien" in lowered


def tecno_needs_quote(data: dict[str, Any]) -> bool:
    rtm = data.get("rtm") or {}
    if bool(rtm.get("debePagarRTM")):
        return True
    if not bool(rtm.get("tieneRTMVigente")):
        return False
    dias = rtm.get("diasRestantes")
    return isinstance(dias, int) and dias <= 30


def soat_needs_quote(data: dict[str, Any]) -> bool:
    soat = data.get("soat") or {}
    if not bool(soat.get("vigente", True)):
        return True
    dias = soat.get("diasRestantes")
    return isinstance(dias, int) and dias <= 30


def format_multas_response(data: dict[str, Any]) -> str:
    parts: list[str] = []

    simit = data.get("simit") if isinstance(data.get("simit"), dict) else data
    if isinstance(simit, dict):
        if not simit.get("tieneMultas"):
            parts.append("En *SIMIT* no aparecen multas activas para ese documento.")
        else:
            resumen = simit.get("resumen") or {}
            total = resumen.get("total") or "sin total claro"
            comparendos = resumen.get("comparendos", 0)
            multas = resumen.get("multas", 0)
            parts.append(
                f"En *SIMIT* aparecen multas/comparendos: total *${total}* "
                f"({comparendos} comparendos, {multas} multas)."
            )

    local = data.get("local") if isinstance(data.get("local"), dict) else None
    if local:
        city = str(local.get("city") or "").strip() or "esa ciudad"
        if local.get("consulted"):
            if local.get("tieneMultas"):
                resumen = local.get("resumen") or {}
                total = resumen.get("total")
                detail_bits = _format_local_multa_details(local.get("detalles"))
                if isinstance(total, int) and total > 0:
                    parts.append(
                        f"En *{city}* (portal local) hay registros: total *${total}*."
                    )
                else:
                    parts.append(
                        f"En *{city}* (portal local) hay registros "
                        f"(pueden estar en audiencia o sin valor liquidado)."
                    )
                if detail_bits:
                    parts.append(detail_bits)
            else:
                parts.append(f"En el portal de *{city}* no aparecen pendientes adicionales.")
        portal_url = str(local.get("portalUrl") or "").strip()
        if portal_url:
            parts.append(f"Por si acaso tambien puedes revisarla aqui: {portal_url}")

    if not parts:
        return "No pude armar un resumen claro de multas. Verifica la cedula y la ciudad."
    return " ".join(parts)


def _format_local_multa_details(detalles: object) -> str:
    if not isinstance(detalles, list) or not detalles:
        return ""
    snippets: list[str] = []
    for item in detalles[:3]:
        if not isinstance(item, dict):
            continue
        codigo = str(item.get("codigo") or "").strip()
        placa = str(item.get("placa") or "").strip()
        estado = str(item.get("estado") or "").strip()
        infraccion = str(item.get("infraccion") or item.get("Infracción") or "").strip()
        fecha = str(item.get("fecha") or "").strip()
        tipo = str(item.get("tipo") or "").strip().lower()
        valor = str(item.get("valor") or "").strip()

        bits: list[str] = []
        if infraccion and codigo and codigo.upper() in infraccion.upper():
            bits.append(infraccion)
        elif codigo and infraccion:
            bits.append(f"{codigo} {infraccion}")
        elif codigo:
            bits.append(codigo)
        elif infraccion:
            bits.append(infraccion[:90])

        if placa:
            bits.append(f"placa {placa}")
        if tipo in {"fotodeteccion", "fotodetección", "fotomulta"}:
            bits.append("fotodeteccion")
        if fecha:
            bits.append(fecha)
        if estado:
            bits.append(f"estado {estado}")
        if valor:
            bits.append(f"valor {valor}")
        if bits:
            snippets.append(", ".join(bits))
    if not snippets:
        return ""
    return "Detalle: " + "; ".join(snippets) + "."


def format_runt_profile_document_request() -> str:
    return (
        f"Claro, con gusto. Pasame la *cedula* como el siguiente ejemplo por favor "
        f"{VEHICLE_DOCUMENT_EXAMPLE} 😊"
    )


def format_runt_profile_response(data: dict[str, Any]) -> str:
    if not data.get("ok"):
        return "No pude traer el perfil RUNT en este momento. Verifica la cedula y lo intento de nuevo."

    payload = data.get("data") if isinstance(data.get("data"), dict) else {}
    tail = data.get("documentoTail") or ""
    name = payload.get("nombre") or payload.get("nombreCompleto") or payload.get("ciudadano")
    licenses = _first_list(payload, ("licencias", "licenciasConduccion", "licencias_conduccion"))
    flat_categories = _first_list(payload, ("categorias",))
    fines = _first_list(payload, ("comparendos", "multas", "sanciones"))

    parts: list[str] = []
    subject = f"documento terminado en *{tail}*" if tail else "ese documento"
    if name:
        parts.append(f"En RUNT aparece *{name}* para el {subject}.")
    else:
        parts.append(f"Ya consulte el perfil RUNT para el {subject}.")

    estado_persona = payload.get("estadoPersona") or payload.get("estado_persona")
    estado_conductor = payload.get("estadoConductor") or payload.get("estado_conductor")
    status_bits = []
    if estado_persona:
        status_bits.append(f"persona {estado_persona}")
    if estado_conductor:
        status_bits.append(f"conductor {estado_conductor}")
    if status_bits:
        parts.append("Estado: " + ", ".join(str(value) for value in status_bits) + ".")

    category_lines = _format_runt_license_categories(licenses, flat_categories)
    if category_lines:
        parts.append("Categorias: " + "; ".join(category_lines) + ".")
    elif licenses:
        license_bits = []
        for item in licenses[:3]:
            if not isinstance(item, dict):
                continue
            status = item.get("estado") or item.get("estadoLicencia")
            ot = item.get("ot")
            bit = "licencia"
            if status:
                bit += f" {status}"
            if ot:
                bit += f" ({ot})"
            license_bits.append(bit)
        if license_bits:
            parts.append("Licencias: " + "; ".join(license_bits) + ".")

    if fines:
        parts.append(f"Tambien veo {len(fines)} registro(s) de comparendos/multas en el perfil.")

    if not category_lines and not licenses and not fines:
        parts.append("No me llego un detalle claro de licencias o categorias en la respuesta.")

    return " ".join(parts)


def _format_runt_license_categories(
    licenses: list[Any],
    flat_categories: list[Any],
) -> list[str]:
    lines: list[str] = []
    for item in licenses[:4]:
        if not isinstance(item, dict):
            continue
        license_status = item.get("estado") or item.get("vigencia") or item.get("estadoLicencia")
        nested = item.get("categorias")
        if isinstance(nested, list) and nested:
            for category in nested[:6]:
                if not isinstance(category, dict):
                    continue
                line = _format_category_line(category, license_status=str(license_status) if license_status else None)
                if line:
                    lines.append(line)
            continue
        # Legacy flat license row without nested categorias.
        category = item.get("categoria") or item.get("clase") or item.get("tipo")
        if category:
            venc = (
                item.get("fechaVencimiento")
                or item.get("fecha_vencimiento")
                or item.get("vencimiento")
            )
            bit = str(category)
            if license_status:
                bit += f" ({license_status})"
            if venc:
                bit += f", vence {venc}"
            lines.append(bit)

    if not lines:
        for category in flat_categories[:6]:
            if isinstance(category, dict):
                line = _format_category_line(category)
                if line:
                    lines.append(line)
            elif category:
                lines.append(str(category))
    return lines


def _format_category_line(category: dict[str, Any], *, license_status: str | None = None) -> str | None:
    code = category.get("categoria") or category.get("clase") or category.get("tipo")
    if not code:
        return None
    venc = (
        category.get("fechaVencimiento")
        or category.get("fecha_vencimiento")
        or category.get("vencimiento")
    )
    status = category.get("estado") or license_status
    bit = str(code)
    if status:
        bit += f" ({status})"
    if venc:
        bit += f", vence {venc}"
    return bit


def _first_list(payload: dict[str, Any], keys: tuple[str, ...]) -> list[Any]:
    for key in keys:
        value = payload.get(key)
        if isinstance(value, list):
            return value
    return []


def _format_distance(distance_km: object) -> str | None:
    if distance_km is None:
        return None
    try:
        km = float(distance_km)
    except (TypeError, ValueError):
        return None
    if km < 1:
        return f"{int(round(km * 1000))} m aprox. (linea recta)"
    if km < 10:
        return f"{km:.1f} km aprox. (linea recta)"
    return f"{int(round(km))} km aprox. (linea recta)"


def _tipo_label(place: dict[str, object]) -> str:
    kind_raw = str(place.get("kind") or "").strip().upper()
    return TIPO_LABELS.get(kind_raw, kind_raw or "Centro")


def format_place_response(place: dict[str, object]) -> str:
    tipo = _tipo_label(place)
    nombre = str(place.get("name") or "").strip() or "Centro"
    direccion = str(place.get("address") or "").strip()
    ciudad = str(place.get("city") or "").strip()
    distancia = _format_distance(place.get("distance_km"))

    lines = [
        "Con la ubicacion que mandaste, este es el centro afiliado Civi que mejor encaja:",
        f"*{tipo}*",
        f"*{nombre}*",
    ]
    if direccion:
        lines.append(f"Direccion: {direccion}")
    if ciudad:
        lines.append(f"Ciudad: {ciudad}")
    if distancia:
        lines.append(f"Distancia: {distancia}")
    lines.append("Te sirve o buscamos otra opcion afiliada?")
    return "\n".join(lines)


def format_place_options_response(places: list[dict[str, object]], *, starts_at: str | None = None) -> str:
    options: list[str] = []
    tipo_hint: str | None = None
    for idx, place in enumerate(places[:5], start=1):
        nombre = str(place.get("name") or "").strip() or "Centro"
        ciudad = str(place.get("city") or "").strip()
        direccion = str(place.get("address") or "").strip()
        distancia = _format_distance(place.get("distance_km"))
        if tipo_hint is None:
            tipo_hint = _tipo_label(place)
        parts = [f"{idx}. *{nombre}*"]
        if direccion:
            parts.append(f"   Direccion: {direccion}")
        if ciudad:
            parts.append(f"   Ciudad: {ciudad}")
        if distancia:
            parts.append(f"   Distancia: {distancia}")
        options.append("\n".join(parts))

    header = (
        f"Estos son centros afiliados Civi de *{tipo_hint}* cerca de ti:"
        if tipo_hint
        else "Estos son centros afiliados Civi cerca de ti:"
    )
    suffix = (
        f"Ya tengo la fecha *{starts_at}*. Dime el numero o el nombre del centro que prefieres."
        if starts_at
        else f"Dime el numero o el nombre del centro que prefieres y la fecha, por ejemplo {DATE_EXAMPLES}."
    )
    return f"{header}\n" + "\n".join(options) + f"\n{suffix}"


def format_place_comparison_response(places: list[dict[str, object]]) -> str:
    """Deterministic advice among listed affiliates: prefer closer distance, no invented quality reviews."""
    if not places:
        return "No tengo centros en la lista para comparar. Comparte ubicacion o ciudad y te busco opciones."

    ranked: list[tuple[float, dict[str, object]]] = []
    for place in places:
        raw = place.get("distance_km")
        try:
            distance = float(raw) if raw is not None else float("inf")
        except (TypeError, ValueError):
            distance = float("inf")
        ranked.append((distance, place))
    ranked.sort(key=lambda item: item[0])
    best_distance, best = ranked[0]
    best_name = str(best.get("name") or "ese centro").strip()
    best_city = str(best.get("city") or "").strip()
    best_dist_label = _format_distance(best.get("distance_km"))

    lines = [
        "Entre estos afiliados Civi no invento cual es 'mejor' en calidad (no tengo reseñas).",
        "Por cercania, el que mas conviene suele ser:",
        f"*{best_name}*" + (f" ({best_city})" if best_city else ""),
    ]
    if best_dist_label:
        lines.append(f"Distancia: {best_dist_label}.")
    if len(ranked) > 1 and ranked[1][0] != float("inf"):
        other = ranked[1][1]
        other_name = str(other.get("name") or "el otro").strip()
        other_dist = _format_distance(other.get("distance_km"))
        if other_dist and best_distance != float("inf"):
            lines.append(f"La siguiente opcion es *{other_name}* a {other_dist}.")
    lines.append("Si te late, dime el *numero* o el *nombre* del centro y seguimos.")
    return "\n".join(lines)


def format_pending_place_date_request(place: dict[str, object]) -> str:
    nombre = str(place.get("name") or "").strip() or "el centro"
    ciudad = str(place.get("city") or "").strip()
    lugar = f"*{nombre}* en {ciudad}" if ciudad else f"*{nombre}*"
    return f"Listo, usamos {lugar}. Cuando quieras, dime fecha y hora, por ejemplo {DATE_EXAMPLES}."


def format_appointment_response(appointment: dict[str, object]) -> str:
    place = appointment.get("place") or {}
    status = str(appointment.get("status") or "")
    if status == "pending_partner":
        return (
            f"Listo, solicite la cita *#{appointment.get('id')}* para *{appointment.get('starts_at')}* "
            f"en *{place.get('name')}*, {place.get('address')}. "
            "El centro afiliado debe confirmarla; te aviso apenas respondan."
        )
    return (
        f"Listo, cita *#{appointment.get('id')}* confirmada para *{appointment.get('starts_at')}* en "
        f"*{place.get('name')}*, {place.get('address')}."
    )


def format_no_affiliate_coverage() -> str:
    return (
        "Aun no tengo afiliados Civi en tu zona para agendar. "
        "Con gusto te oriento sobre el tramite o te paso con un asesor."
    )


def format_partner_decision_response(*, action: str, appointment_id: int, success: bool, error: str | None = None) -> str:
    if success:
        if action == "confirmar":
            return f"Listo, cita {appointment_id} confirmada. Ya avise al cliente."
        return f"Listo, cita {appointment_id} rechazada. Ya avise al cliente."
    if error == "not_found":
        return f"No encontre la cita {appointment_id}. Revisa el numero y lo intentamos."
    if error == "not_pending":
        return f"La cita {appointment_id} ya no esta pendiente de confirmacion."
    return f"No pude procesar la cita {appointment_id}. Intentemoslo de nuevo."


def format_appointments_list(data: dict[str, object]) -> str:
    appointments = data.get("appointments") or []
    if not appointments:
        return "Por ahora no tienes citas activas registradas."
    first = appointments[0]
    place = first.get("place") or {}
    return f"Tu proxima cita es el *{first.get('starts_at')}* en *{place.get('name')}*."


def format_cancel_appointment_response(data: dict[str, object]) -> str:
    if not data.get("success"):
        return "No encontre esa cita activa para cancelar. Revisa el ID y lo intentamos de nuevo."
    appointment = data.get("appointment") if isinstance(data.get("appointment"), dict) else {}
    return f"Listo, cancele la cita *{appointment.get('id')}*."


def format_reminder_response(data: dict[str, object]) -> str:
    reminder = data.get("reminder") if isinstance(data.get("reminder"), dict) else {}
    remind_at = reminder.get("remind_at")
    if remind_at:
        return f"Listo, te recuerdo el *{remind_at}*."
    return "Listo, recordatorio programado."


def format_quote_response(data: dict[str, object]) -> str:
    message = data.get("message")
    if isinstance(message, str) and message.strip():
        return f"{message.strip()} {data.get('disclaimer')}".strip()
    price_cop = data.get("price_cop")
    if isinstance(price_cop, int) and price_cop > 0:
        return (
            f"Referencia para *{data.get('service_type')}*: *${price_cop}* "
            f"{data.get('currency', 'COP')}. {data.get('disclaimer')}"
        )
    return (
        f"Referencia para *{data.get('service_type')}*: entre "
        f"*${data.get('price_min')}* y *${data.get('price_max')}* {data.get('currency', 'COP')}. "
        f"{data.get('disclaimer')}"
    )


def format_knowledge_response(data: dict[str, object]) -> str:
    if not data.get("success"):
        available = data.get("available_topics") or []
        if available:
            return "Puedo responder ese tema si lo enfocamos en: " + ", ".join(str(item) for item in available[:6]) + "."
        return str(data.get("message") or "No tengo ese tema validado en la base de conocimiento.")
    body = data.get("body")
    if isinstance(body, str) and body.strip():
        return body.strip()
    return "No tengo una respuesta validada para ese tema."


def format_city_knowledge_response(data: dict[str, object]) -> str:
    city = data.get("city") or "esa ciudad"
    if not data.get("enabled"):
        nearby = data.get("nearby_cities") or []
        if nearby:
            return (
                f"Aun no tengo cobertura operativa cargada para tecnomecanica en {city}. "
                f"Ciudades disponibles: {', '.join(str(item) for item in nearby)}."
            )
        return f"Aun no tengo cobertura operativa cargada para tecnomecanica en {city}."

    total_places = data.get("total_places", 0)
    total_partners = data.get("total_partners", 0)
    notes = str(data.get("notes") or "").strip()
    return (
        f"En {city} tengo {total_places} CDA(s) cargado(s) para tecnomecanica, "
        f"{total_partners} aliado(s). {notes}"
    ).strip()


def format_payment_intent_response(data: dict[str, object]) -> str:
    if data.get("payment_url"):
        return f"Listo. Te dejo el enlace de pago: {data.get('payment_url')}"
    return "Puedo preparar el pago, pero el proveedor de pagos aun no esta activo en este entorno."


def format_handoff_response(data: dict[str, object]) -> str:
    return str(data.get("message") or "Te paso con un asesor.")


def format_infraccion_detail_response(data: dict[str, object]) -> str:
    if not data.get("success"):
        return str(data.get("message") or "No encontre esa infraccion en la base de datos.")

    codigo = str(data.get("codigo") or "")
    descripcion = str(data.get("descripcion") or "")
    categoria = str(data.get("categoria") or "")
    monto = data.get("monto_cop_2026")
    smdlv = data.get("smdlv")
    articulo = str(data.get("articulo") or "")
    admite_descuento = bool(data.get("admite_descuento_curso"))
    consejo = str(data.get("consejo") or "")

    parts = [
        f"Infraccion *{codigo}* (categoria {categoria}): {descripcion}.",
    ]
    if monto:
        smdlv_text = f" ({smdlv} SMDLV)" if smdlv else ""
        parts.append(f"Valor aproximado 2026: *${monto:,.0f} COP*{smdlv_text}.")
    if articulo:
        parts.append(f"Base legal: {articulo}.")
    if admite_descuento:
        parts.append(
            "Esta infraccion *SI admite descuento* con curso CIA (50% en primeros 5 dias habiles "
            "si fue en via, 11 dias habiles si fue fotomulta)."
        )
    else:
        parts.append("Esta infraccion *NO admite descuento* por curso CIA.")
    if consejo:
        parts.append(consejo)

    return " ".join(parts)
