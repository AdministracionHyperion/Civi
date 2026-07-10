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


SOAT_INFO: dict[str, KnowledgeItem] = {
    "que_cubre": KnowledgeItem(
        topic="que_cubre",
        title="Que cubre el SOAT",
        body=(
            "El SOAT cubre ATENCION MEDICA a todas las victimas de un accidente de transito, sin importar quien "
            "tuvo la culpa. Cubre 4 cosas: (1) Gastos medicos, quirurgicos y hospitalarios hasta $36.749.788 "
            "(701.68 UVT en 2026). (2) Incapacidad permanente hasta $10.505.430 (180 SMDLV) segun el porcentaje "
            "de perdida de capacidad laboral. (3) Muerte y gastos funerarios hasta $43.772.625 (750 SMDLV). "
            "(4) Transporte de la victima hasta $459.320 (8.77 UVT). "
            "IMPORTANTE: el SOAT NO cubre danos materiales al vehiculo ni a bienes de terceros. Para eso "
            "necesitas un seguro de responsabilidad civil o todo riesgo."
        ),
    ),
    "en_accidente": KnowledgeItem(
        topic="en_accidente",
        title="Que hacer con el SOAT en un accidente",
        body=(
            "Si tuviste un accidente: (1) Asegurate de que todos esten bien, si hay heridos llama al 123. "
            "(2) No muevas los vehiculos si hay lesionados; si solo hay danos materiales, mueve los carros "
            "para no obstruir la via (Ley 2251 de 2022). (3) Reporta el accidente a la aseguradora del SOAT "
            "lo antes posible. (4) Guarda la documentacion medica y facturas. "
            "El SOAT cubre a peatones, pasajeros y conductores de todos los vehiculos involucrados. "
            "Puedes reclamar aunque no tengas SOAT vigente: la atencion medica de urgencia esta garantizada."
        ),
    ),
    "cuanto_cubre": KnowledgeItem(
        topic="cuanto_cubre",
        title="Montos de cobertura SOAT 2026",
        body=(
            "Coberturas maximas del SOAT para accidentes en 2026 (SMDLV=$58.364, UVT=$52.374): "
            "Gastos medicos: hasta $36.749.788. "
            "Incapacidad permanente: hasta $10.505.430 (proporcional al % de perdida). "
            "Muerte: $43.772.625 (incluye gastos funerarios). "
            "Transporte: hasta $459.320. "
            "Estos valores se actualizan cada ano con el SMDLV y la UVT."
        ),
    ),
    "sin_soat": KnowledgeItem(
        topic="sin_soat",
        title="Consecuencias de no tener SOAT",
        body=(
            "Conducir sin SOAT vigente es infraccion categoria D (D02): 30 SMDLV de multa "
            "(aproximadamente $1.750.920 en 2026) e inmovilizacion del vehiculo. "
            "Ademas, si causas un accidente sin SOAT, eres personalmente responsable de TODOS los gastos "
            "medicos de las victimas, sin limite. El SOAT es obligatorio para todo vehiculo que circule en Colombia."
        ),
    ),
    "contacto_emergencia": KnowledgeItem(
        topic="contacto_emergencia",
        title="Numeros de emergencia en accidentes",
        body=(
            "En caso de accidente de transito en Colombia: "
            "Linea unica de emergencias: 123 (policia, ambulancia, transito). "
            "Policia de Transito: #767. Cruz Roja: 132. Bomberos: 119. "
            "Tambien puedes contactar a tu aseguradora SOAT; muchas tienen app con asistencia en via 24/7. "
            "Si el accidente es grave, no muevas a los heridos a menos que haya peligro inminente de explosion o incendio."
        ),
    ),
}

ACCIDENTE_INFO: dict[str, KnowledgeItem] = {
    "checklist": KnowledgeItem(
        topic="checklist",
        title="Checklist post-accidente",
        body=(
            "PROTOCOLO DE ACCIDENTE DE TRANSITO EN COLOMBIA (Ley 2251/2022): "
            "(1) MANTENE LA CALMA y verifica si hay heridos. Si los hay, llama al 123 YA. "
            "(2) SIN HERIDOS (choque simple): toma FOTOS de los danos, posicion de los vehiculos, placas y "
            "senales cercanas. LUEGO MOVE los vehiculos a un costado para no obstruir la via. Es OBLIGATORIO. "
            "(3) CON HERIDOS: NO MUEVAS NADA. Espera a transito para que levante el IPAT (Informe Policial de "
            "Accidentes de Transito). Te haran prueba de alcoholemia obligatoria. "
            "(4) Intercambia datos: nombre, cedula, telefono y poliza de seguro con los otros conductores. "
            "(5) Llama a tu aseguradora para reportar el siniestro. "
            "(6) NO aceptes dinero en efectivo en el lugar sin consultar con tu aseguradora."
        ),
    ),
    "heridos": KnowledgeItem(
        topic="heridos",
        title="Que hacer si hay heridos",
        body=(
            "Si hay heridos en el accidente: "
            "NO muevas a los heridos a menos que haya peligro inminente (fuego, explosion, inmersion). "
            "Llama al 123 y pide ambulancia indicando cuantos heridos hay. "
            "No les des agua, comida ni medicamentos. Si hay sangrado, aplica presion con un panio limpio. "
            "Espera a los paramedicos y a la autoridad de transito. "
            "La prueba de alcoholemia es OBLIGATORIA para todos los conductores involucrados. "
            "El SOAT cubre los gastos medicos de TODAS las victimas, sin importar quien tuvo la culpa."
        ),
    ),
    "documentos_necesarios": KnowledgeItem(
        topic="documentos_necesarios",
        title="Documentos necesarios tras un accidente",
        body=(
            "Despues de un accidente de transito necesitas: "
            "(1) Tu cedula de ciudadania. (2) Licencia de conduccion vigente. (3) SOAT vigente (fisico o digital). "
            "(4) Tarjeta de propiedad del vehiculo. "
            "(5) Si hubo lesionados, el IPAT que levanta la autoridad de transito. "
            "(6) Datos del otro conductor: nombre, cedula, telefono, placa, aseguradora y numero de poliza. "
            "(7) Fotos y videos que tomaste en el lugar. "
            "Si solo hubo danos materiales, el IPAT ya no es obligatorio (Ley 2251/2022)."
        ),
    ),
    "responsabilidad": KnowledgeItem(
        topic="responsabilidad",
        title="Quien paga que en un accidente",
        body=(
            "En un accidente de transito en Colombia: "
            "LESIONES PERSONALES: las paga el SOAT de cada vehiculo involucrado (hasta los topes de cobertura). "
            "DANOS MATERIALES: los paga el conductor responsable, ya sea de su bolsillo o con su seguro voluntario "
            "(responsabilidad civil o todo riesgo). El SOAT NO cubre danos a vehiculos ni bienes. "
            "Si el responsable no tiene seguro ni dinero, puedes acudir a un centro de conciliacion autorizado o "
            "iniciar un proceso civil. Si hay acuerdo entre las partes, pueden conciliar en el sitio sin necesidad "
            "de ir a transito (solo si no hay heridos)."
        ),
    ),
}

INFRACCIONES_INFO: dict[str, KnowledgeItem] = {
    "categorias": KnowledgeItem(
        topic="categorias",
        title="Categorias de infracciones y sus valores 2026",
        body=(
            "Las infracciones de transito en Colombia se clasifican asi (valores 2026, 1 SMDLV=$58.364, "
            "basado en Ley 769/2002 y actualizaciones): "
            "A: 4 SMDLV ($233.456) - infracciones leves (ej. no usar luces A06). "
            "B: 8 SMDLV ($466.912) - infracciones medias. "
            "C: 15 SMDLV ($875.460) - mal parqueo C02, pico y placa C14, celular C38, tecno C35, exceso velocidad C29. "
            "D: 30 SMDLV ($1.750.920) - semaforo en rojo D04, sin SOAT D02, ruido/emisiones D17. "
            "E: 45 SMDLV ($2.626.380) - infracciones muy graves (ej. embriaguez grave / zona escolar). "
            "Los montos de multa son fijos por categoria, no hay rangos. "
            "La mayoria admite descuento 50% o 25% si pagas y haces curso CIA dentro de los plazos."
        ),
    ),
    "leer_multa": KnowledgeItem(
        topic="leer_multa",
        title="Como leer un comparendo",
        body=(
            "Un comparendo de transito en Colombia tiene estos elementos clave: "
            "(1) CODIGO de infraccion: letra y numero (ej: C35, D04, C38). La letra indica categoria y valor. "
            "(2) DESCRIPCION: que norma exacta infringiste. (3) ARTICULO de la ley base (Ley 769/2002). "
            "(4) FECHA y LUGAR de la infraccion. (5) PLACA y DATOS del conductor. "
            "(6) VALOR en SMDLV y pesos. "
            "(7) Si admite descuento: 50% en primeros 5 dias habiles (en via) u 11 dias habiles (fotomulta) "
            "desde notificacion, haciendo ademas un curso CIA. "
            "Puedes consultar tus multas en SIMIT con tu numero de cedula."
        ),
    ),
    "luces": KnowledgeItem(
        topic="luces",
        title="Infraccion por luces (A06)",
        body=(
            "Infraccion A06: Transitar sin dispositivos luminosos requeridos. Categoria A, "
            "multa: 4 SMDLV ($233.456 en 2026). Aplica si tienes farolas, stops, direccionales o luces "
            "principales danadas, fundidas o ausentes. En motos tambien por falta de luces reglamentarias. "
            "Vale curso CIA para descuento. Tip: carga bombillos de repuesto, una luz fundida te puede costar cara."
        ),
    ),
    "cinturon": KnowledgeItem(
        topic="cinturon",
        title="Infraccion por cinturon (C06)",
        body=(
            "Infraccion C06: No usar el cinturon de seguridad. Categoria C, "
            "multa: 15 SMDLV ($875.460 en 2026). Aplica para conductor y TODOS los pasajeros, "
            "adelante y atras. En buses el conductor responde por los pasajeros. "
            "Tambien si el cinturon esta danado. Vale curso CIA para descuento. "
            "El cinturon reduce hasta 50% el riesgo de muerte en accidente."
        ),
    ),
    "embriaguez": KnowledgeItem(
        topic="embriaguez",
        title="Infraccion por embriaguez",
        body=(
            "Conducir bajo alcohol se sanciona con multas altas, suspension de licencia y, en grados graves, "
            "puede pasar a delito penal (Ley 1696 de 2013). "
            "EMBRIAGUEZ NO ADMITE DESCUENTO por curso CIA. "
            "Si hay lesionados o muertos, la responsabilidad penal se suma a la sancion de transito. "
            "Para el valor exacto de tu caso, consulta el comparendo en SIMIT o dime el codigo."
        ),
    ),
    "estacionamiento": KnowledgeItem(
        topic="estacionamiento",
        title="Infraccion por mal estacionamiento (C02)",
        body=(
            "Infraccion C02: Estacionar en sitios prohibidos. Categoria C, "
            "multa: 15 SMDLV ($875.460 en 2026) + INMOVILIZACION y grua. Incluye estacionar en: "
            "andenes, zonas verdes, via arterial, curva, puente, tunel, zona peatonal, "
            "entrada de garaje, frente a hidrantes, o donde la senal lo prohiba. "
            "Vale curso CIA para descuento. Nota: C35 es tecnomecanica vencida, no mal parqueo."
        ),
    ),
    "celular": KnowledgeItem(
        topic="celular",
        title="Infraccion por celular al volante (C38)",
        body=(
            "Infraccion C38: Usar celular al conducir sin manos libres. Categoria C, "
            "multa: 15 SMDLV ($875.460 en 2026). Aplica si manipulas el celular mientras manejas. "
            "Solo se permite con manos libres o Bluetooth. Vale curso CIA para descuento."
        ),
    ),
    "semaforo": KnowledgeItem(
        topic="semaforo",
        title="Infraccion por semaforo en rojo (D04)",
        body=(
            "Infraccion D04: No detenerse ante luz roja o amarilla, senal PARE o intermitente rojo. "
            "Categoria D, multa: 30 SMDLV ($1.750.920 en 2026). "
            "No confundir con D02 (sin SOAT). La suspension de licencia no es automatica en la primera vez: "
            "el Art. 124 del CNT la asocia a reincidencia en un periodo de 6 meses. "
            "Vale curso CIA para descuento si aplica a tu caso."
        ),
    ),
    "espejos": KnowledgeItem(
        topic="espejos",
        title="Moto sin espejos o dispositivos (C24)",
        body=(
            "Conducir moto sin espejos retrovisores u omitiendo normas del Codigo suele sancionarse como "
            "C24 (categoria C): 15 SMDLV ($875.460 en 2026). "
            "No es C02 (C02 es mal estacionamiento) ni categoria B. Vale curso CIA para descuento."
        ),
    ),
    "zona_restringida": KnowledgeItem(
        topic="zona_restringida",
        title="Zona prohibida / pico y placa (C14)",
        body=(
            "Infraccion C14: Transitar por sitios u horas restringidas (pico y placa / zonas prohibidas). "
            "Categoria C, multa: 15 SMDLV ($875.460 en 2026) + posible inmovilizacion. "
            "No es D04 (semaforo) ni C35 (tecnomecanica). Vale curso CIA para descuento."
        ),
    ),
    "chaleco": KnowledgeItem(
        topic="chaleco",
        title="Chaleco o kit reflectivo (C11/C14)",
        body=(
            "Si te refieres al kit de carretera del carro (triangulos/chaleco/extintor), aplica C11: "
            "15 SMDLV ($875.460 en 2026). "
            "Si es restriccion local de moto por no portar elementos reflectivos en horario/zona restringida, "
            "puede aplicarse C14 (tambien 15 SMDLV). En ambos casos es categoria C, no 8 SMDLV."
        ),
    ),
    "gafas": KnowledgeItem(
        topic="gafas",
        title="Conducir sin gafas de la licencia (C13)",
        body=(
            "Si tu licencia exige gafas/lentes y conduces sin ellas, aplica C13: "
            "categoria C, 15 SMDLV ($875.460 en 2026). El valor es fijo, no hay rango de precios. "
            "Vale curso CIA para descuento."
        ),
    ),
    "ruido": KnowledgeItem(
        topic="ruido",
        title="Escape ruidoso / emisiones (D17)",
        body=(
            "Infraccion D17: normas de emisiones o generacion de ruido (escape modificado/exosto). "
            "Categoria D, multa: 30 SMDLV ($1.750.920 en 2026) + posible inmovilizacion hasta corregir. "
            "La normativa tecnica de ruido se ha endurecido (incl. Ley Antirruido 2450/2025); "
            "el limite exacto en dB lo confirma la autoridad local o la medicion oficial. "
            "No inventes rangos: el valor de la multa D17 es fijo por categoria."
        ),
    ),
    "velocidad": KnowledgeItem(
        topic="velocidad",
        title="Infracciones por exceso de velocidad",
        body=(
            "Exceso de velocidad tipico: C29 (conducir a velocidad superior a la maxima), "
            "categoria C, 15 SMDLV ($875.460 en 2026). "
            "Limites generales de referencia: urbano 50 km/h, rural 80 km/h, autopista segun la via. "
            "No confundir con D02 (D02 es sin SOAT). Para el codigo exacto de tu comparendo, consulta SIMIT."
        ),
    ),
    "varado": KnowledgeItem(
        topic="varado",
        title="Vehiculo varado o averiado en via",
        body=(
            "Si tu vehiculo se vara en via publica: "
            "(1) Luces de emergencia + triangulos a 30m (ciudad) o 50-100m (carretera). "
            "(2) Si obstruyes o dejas el vehiculo mal ubicado, puedes caer en C02 "
            "(mal estacionamiento / sitio prohibido): 15 SMDLV ($875.460) + grua. "
            "(3) Llama a tu seguro o grua. En autopista espera detras de la defensa metalica. "
            "Policia de Carreteras: #767."
        ),
    ),
    "soat_falta": KnowledgeItem(
        topic="soat_falta",
        title="Multa por no tener SOAT (D02)",
        body=(
            "Infraccion D02: Conducir sin SOAT vigente. Categoria D, "
            "multa: 30 SMDLV ($1.750.920 en 2026) + INMOVILIZACION del vehiculo. "
            "No confundir con D04 (semaforo en rojo). "
            "El SOAT es obligatorio para circular. Puedes comprar SOAT digital en minutos."
        ),
    ),
}


DOMAIN_ITEMS = {
    "tecnomecanica": TECNOMECANICA_INFO,
    "cia": CIA_INFO,
    "soat": SOAT_INFO,
    "accidente": ACCIDENTE_INFO,
    "infracciones": INFRACCIONES_INFO,
}

DOMAIN_ALIASES = {
    "tecno": "tecnomecanica",
    "tecnomecanica": "tecnomecanica",
    "rtm": "tecnomecanica",
    "cda": "tecnomecanica",
    "curso": "cia",
    "curso_multa": "cia",
    "multa": "cia",
    "comparendo": "cia",
    "fotomulta": "cia",
    "cia": "cia",
    "soat": "soat",
    "seguro": "soat",
    "accidente": "accidente",
    "choque": "accidente",
    "siniestro": "accidente",
    "colision": "accidente",
    "estrellon": "accidente",
    "estrellar": "accidente",
    "danos": "accidente",
    "daño": "accidente",
    "chocar": "accidente",
    "golpe": "accidente",
    "infraccion": "infracciones",
    "infracciones": "infracciones",
    "codigo": "infracciones",
    "leer_multa": "infracciones",
    "leer comparendo": "infracciones",
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
