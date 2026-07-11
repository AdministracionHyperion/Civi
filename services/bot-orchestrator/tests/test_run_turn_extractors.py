import json

import httpx
import pytest
from fastapi.testclient import TestClient

from bot_orchestrator.adapters.outbound.llm_provider import (
    OpenAICompatibleChatLLMProvider,
    OpenAIResponsesLLMProvider,
    llm_provider_from_env,
)
from bot_orchestrator.main import app
from bot_orchestrator.prompts.loader import build_system_prompt, load_prompt_part
from bot_orchestrator.slices.run_turn.extractors import (
    extract_appointment_id,
    extract_city,
    extract_displacement,
    extract_document,
    extract_infraction_code,
    extract_model_year,
    extract_partner_decision,
    extract_place_selection,
    extract_plate,
    extract_start_iso,
    extract_vehicle_type,
    knowledge_domain_for_text,
    knowledge_topic_for_text,
    normalize_infraccion_query,
    procedure_for_text,
    quote_service_for_text,
    wants_appointment,
    wants_cancel_appointment,
    wants_city_coverage,
    wants_alternative_places,
    wants_general_multas_city,
    wants_general_traffic_question,
    wants_handoff,
    wants_infraccion_lookup,
    wants_knowledge,
    wants_multas,
    wants_payment,
    wants_place_comparison,
    wants_quote,
    wants_reminder,
    wants_runt_profile,
    wants_situational_advice,
    wants_soat,
    wants_vigencia,
)
from bot_orchestrator.slices.run_turn.formatters import (
    format_multas_city_request,
    format_multas_query_request,
    format_multas_response,
    format_place_comparison_response,
    format_quote_response,
    format_runt_profile_response,
    format_vehicle_slots_request,
    format_vigencia_response,
)
from bot_orchestrator.shared.appointment_selection import (
    appointment_selection_store,
    last_vehicle_slots_store,
    vehicle_consult_store,
)
from bot_orchestrator.slices.run_turn.schemas import AgentTurnRequest, AgentTurnResponse
import bot_orchestrator.slices.run_turn.use_case as run_turn_module
from bot_orchestrator.slices.run_turn.use_case import location_for_turn, notification_to_for_turn, run_agent_turn


class FakeLLMProvider:
    last_history: list[dict[str, str]] | None = None

    async def complete(
        self,
        *,
        system_prompt: str,
        user_text: str,
        user_key: str,
        channel: str,
        history: list[dict[str, str]] | None = None,
    ) -> dict[str, object]:
        FakeLLMProvider.last_history = history
        return {"provider_mode": "fake-llm", "text": f"respuesta LLM para {user_text}"}


class FakeQuoteClient:
    calls: list[dict[str, object]] = []

    async def create(self, **payload: object) -> dict[str, object]:
        self.calls.append(payload)
        service_type = str(payload["service_type"])
        if service_type == "infraccion":
            consulta = str(payload.get("consulta") or "").lower()
            codigo = str(payload.get("codigo") or "").upper()
            if (
                any(term in consulta for term in ("me escape", "reten", "evadir", "fuga de"))
                or codigo == "C31"
            ):
                return {
                    "service_type": "infraccion",
                    "price_min": 875460,
                    "price_max": 875460,
                    "price_cop": 875460,
                    "currency": "COP",
                    "message": "Infraccion C31: $875.460 COP referencial 2026.",
                    "disclaimer": "Valor referencial.",
                    "codigo": "C31",
                }
            if (
                any(term in consulta for term in ("exosto", "escape", "silenciador", "exsosto"))
                or codigo == "D17"
            ):
                return {
                    "service_type": "infraccion",
                    "price_min": 1750920,
                    "price_max": 1750920,
                    "price_cop": 1750920,
                    "currency": "COP",
                    "message": "Infraccion D17: $1.750.920 COP referencial 2026.",
                    "disclaimer": "Valor referencial.",
                    "codigo": "D17",
                }
            return {
                "service_type": "infraccion",
                "price_min": 633200,
                "price_max": 633200,
                "price_cop": 633200,
                "currency": "COP",
                "message": "Infraccion D04: $633.200 COP referencial 2026.",
                "disclaimer": "Valor referencial.",
            }
        if service_type == "tecnomecanica":
            return {
                "service_type": "tecnomecanica",
                "price_min": 368853,
                "price_max": 368853,
                "price_cop": 368853,
                "currency": "COP",
                "message": "Tecnomecanica para carro particular 2026: alrededor de $368.853 COP.",
                "disclaimer": "Valor referencial.",
            }
        if service_type == "soat":
            return {
                "service_type": "soat",
                "price_min": 592900,
                "price_max": 592900,
                "price_cop": 592900,
                "currency": "COP",
                "message": "SOAT carro hasta 1500 cc, modelo 2015: $592.900 COP referencial 2026.",
                "disclaimer": "Valor referencial.",
            }
        return {
            "service_type": service_type,
            "price_min": 350000,
            "price_max": 1200000,
            "currency": "COP",
            "disclaimer": "Valor referencial.",
        }


class FakeBillingClient:
    async def create_payment_intent(
        self,
        *,
        user_key: str,
        concept: str,
        amount: int,
        currency: str = "COP",
    ) -> dict[str, object]:
        return {"payment_intent_id": "pay_test", "status": "created_without_provider", "amount": amount, "currency": currency}


class FakeHandoffClient:
    async def create(self, *, user_key: str, reason: str, channel: str) -> dict[str, object]:
        return {"handoff_id": "handoff_test", "status": "queued", "message": "Te paso con un asesor."}


class FakeVehicleClient:
    async def check_vigencia(
        self,
        *,
        placa: str,
        documento: str,
        tipo_documento: str = "CC",
    ) -> dict[str, object]:
        return {
            "placa": placa,
            "vehiculo": {
                "placa": placa,
                "marca": "Chevrolet",
                "linea": "Spark",
                "modelo": 2015,
                "claseVehiculo": "AUTOMOVIL",
                "color": "blanco",
                "cilindraje": 1200,
            },
            "soat": {"fechaVencimiento": "01/03/2026", "diasRestantes": -60, "vigente": False},
            "rtm": {
                "tieneRTMVigente": False,
                "debePagarRTM": True,
                "proximaFechaRTM": "10/03/2026",
                "diasRestantes": -60,
                "motivo": "El vehiculo requiere RTM.",
            },
        }

    async def consult_runt_profile(self, *, documento: str) -> dict[str, object]:
        return {
            "ok": True,
            "documentoTail": documento[-4:],
            "data": {
                "nombre": "Persona Demo",
                "estadoPersona": "ACTIVA",
                "estadoConductor": "ACTIVO",
                "licencias": [
                    {
                        "numero": documento,
                        "estado": "ACTIVA",
                        "categorias": [
                            {
                                "categoria": "B1",
                                "fechaExpedicion": "29/11/2024",
                                "fechaVencimiento": "29/11/2034",
                            }
                        ],
                    }
                ],
            },
            "checkedAt": "2026-07-07T00:00:00+00:00",
        }

    async def consult_multas(self, *, documento: str, ciudad: str | None = None) -> dict[str, object]:
        return {
            "success": True,
            "tieneMultas": False,
            "documentoTail": documento[-4:],
            "resumen": {"comparendos": 0, "multas": 0, "total": 0},
            "simit": {
                "tieneMultas": False,
                "resumen": {"comparendos": 0, "multas": 0, "total": 0},
                "mensaje": "Sin pendientes",
                "detalles": [],
                "documentoTail": documento[-4:],
            },
            "local": {
                "city": ciudad,
                "source": "manizales" if ciudad == "Manizales" else None,
                "consulted": ciudad == "Manizales",
                "tieneMultas": False if ciudad == "Manizales" else None,
                "portalUrl": (
                    "https://www.movilidadmanizales.com.co/portal-servicios/"
                    if ciudad == "Manizales"
                    else "https://webfenix.movilidadbogota.gov.co/#/consulta-pagos"
                    if ciudad == "Bogota"
                    else None
                ),
                "resumen": None,
                "mensaje": None,
                "detalles": [],
            },
        }


class FakePlacesClient:
    calls: list[dict[str, object]] = []

    async def find_nearest(
        self,
        *,
        procedure: str,
        city: str | None = None,
        lat: float | None = None,
        lng: float | None = None,
    ) -> dict[str, object]:
        self.calls.append({"procedure": procedure, "city": city, "lat": lat, "lng": lng})
        kind = "CIA" if procedure == "curso_multa" else "CDA"
        return {
            "places": [
                {
                    "id": f"{kind.lower()}-1",
                    "name": f"{kind} Uno",
                    "address": "Calle 1",
                    "city": city or "Bogota",
                    "department": "Cundinamarca",
                    "kind": kind,
                    "distance_km": 1.2,
                },
                {
                    "id": f"{kind.lower()}-2",
                    "name": f"{kind} Dos",
                    "address": "Calle 2",
                    "city": city or "Bogota",
                    "department": "Cundinamarca",
                    "kind": kind,
                    "distance_km": 2.4,
                },
            ]
        }


class FakeAppointmentClient:
    created: list[dict[str, object]] = []
    cancelled: list[dict[str, object]] = []
    decisions: list[dict[str, object]] = []
    _next_id = 88

    async def create(
        self,
        *,
        user_key: str,
        procedure: str,
        starts_at: str,
        place: dict[str, object],
        notification_to: str | None = None,
    ) -> dict[str, object]:
        appointment_id = FakeAppointmentClient._next_id
        FakeAppointmentClient._next_id += 1
        payload = {
            "user_key": user_key,
            "procedure": procedure,
            "starts_at": starts_at,
            "place": place,
            "notification_to": notification_to,
            "id": appointment_id,
        }
        self.created.append(payload)
        return {
            "success": True,
            "appointment": {
                "id": appointment_id,
                "user_key": user_key,
                "status": "pending_partner",
                "starts_at": starts_at,
                "place": place,
            },
            "notification": {"status": "sent", "to": "573009998877", "kind": "partner_request"},
        }

    async def cancel(self, *, user_key: str, appointment_id: int) -> dict[str, object]:
        self.cancelled.append({"user_key": user_key, "appointment_id": appointment_id})
        return {
            "success": True,
            "appointment": {
                "id": appointment_id,
                "user_key": user_key,
                "status": "cancelled",
                "starts_at": "2026-07-10T09:00",
                "place": {"name": "CDA Demo"},
            },
        }

    async def list_for_user(self, *, user_key: str) -> dict[str, object]:
        return {"appointments": []}

    async def confirm(self, *, appointment_id: int) -> dict[str, object]:
        self.decisions.append({"action": "confirm", "appointment_id": appointment_id})
        return {
            "success": True,
            "appointment": {"id": appointment_id, "status": "confirmed"},
            "notifications": {},
        }

    async def reject(self, *, appointment_id: int) -> dict[str, object]:
        self.decisions.append({"action": "reject", "appointment_id": appointment_id})
        return {
            "success": True,
            "appointment": {"id": appointment_id, "status": "rejected"},
            "notifications": {},
        }

class FakeNotificationClient:
    async def schedule_reminder(self, *, user_key: str, to: str, body: str, remind_at: str) -> dict[str, object]:
        return {
            "success": True,
            "reminder": {
                "id": 7,
                "user_key": user_key,
                "to_tail": "****2233",
                "remind_at": remind_at,
                "status": "scheduled",
            },
        }


class FakeKnowledgeClient:
    async def get_info(self, *, domain: str, topic: str) -> dict[str, object]:
        return {
            "success": True,
            "domain": domain,
            "topic": topic,
            "title": "Que llevar",
            "body": "Lleva cedula, tarjeta de propiedad y SOAT vigente.",
            "available_topics": ["que_llevar"],
        }

    async def get_city_info(self, *, city: str, service_type: str = "tecnomecanica") -> dict[str, object]:
        return {
            "success": True,
            "city": city,
            "service_type": service_type,
            "enabled": True,
            "total_places": 1,
            "total_partners": 1,
            "notes": "Cobertura cargada.",
        }


@pytest.fixture(autouse=True)
def clear_pending_appointment_selection() -> None:
    appointment_selection_store.clear_all()
    vehicle_consult_store.clear_all()
    last_vehicle_slots_store.clear_all()
    FakeAppointmentClient.created.clear()
    FakeAppointmentClient.cancelled.clear()
    FakeAppointmentClient.decisions.clear()
    FakeAppointmentClient._next_id = 88
    FakePlacesClient.calls.clear()
    FakeQuoteClient.calls.clear()


def test_extract_plate_and_document() -> None:
    text = "quiero consultar soat de abc123 cedula 123456789"

    assert extract_plate(text) == "ABC123"
    assert extract_document(text) == "123456789"
    assert wants_vigencia(text)


def test_soat_typos_match_vigencia_intent() -> None:
    assert wants_soat("y su soart")
    assert wants_vigencia("y su soart")
    assert wants_soat("revisar el soaat")
    assert wants_soat("SOAT de la moto")


def test_format_vehicle_slots_request_variants() -> None:
    both = format_vehicle_slots_request(need_placa=True, need_documento=True)
    only_placa = format_vehicle_slots_request(need_placa=True, need_documento=False)
    only_doc = format_vehicle_slots_request(need_placa=False, need_documento=True)

    assert both.startswith("Claro, con gusto.")
    assert "ABC123 1234567890" in both
    assert "😊" in both
    assert "ABC123" in only_placa and "1234567890" not in only_placa
    assert "1234567890" in only_doc and "ABC123" not in only_doc


def test_multas_intent() -> None:
    assert wants_multas("tengo comparendos en simit?")
    assert wants_multas("puedes mirar mis multas")
    assert not wants_multas("curso por multa")
    assert wants_general_multas_city("no se, mira general")


def test_handoff_requires_human_signal() -> None:
    assert not wants_handoff("ASESORAME")
    assert not wants_handoff("asesorame")
    assert wants_handoff("quiero hablar con un asesor")
    assert wants_handoff("pasame con un asesor humano")


def test_infraccion_lookup_by_conduct() -> None:
    assert wants_infraccion_lookup("TENGO EL EXOSTO MODIFICADO Y ESO ES ILEGAL")
    assert wants_infraccion_lookup("NOOOO ME ESCAPE")
    assert normalize_infraccion_query("tengo el exsosto mmoficiado") == "tengo el exosto modificado"


def test_runt_profile_intent() -> None:
    assert wants_runt_profile("consulta mi licencia con cedula 123456789")
    assert wants_runt_profile("quiero consultar mi licensia")
    assert wants_runt_profile("consulta mi lisencia")
    assert wants_runt_profile("estado de mi liciencia")
    assert wants_runt_profile("necesito consultar una licenia")
    assert wants_runt_profile("necesito consultar una licencia")
    assert not wants_runt_profile("quiero agendar licencia en Bogota")
    assert not wants_runt_profile("quiero agendar licensia en Bogota")
    assert not wants_runt_profile("necesito un favor")


def test_appointment_extraction() -> None:
    text = "quiero agendar tecnomecanica en Bucaramanga el 2026-07-10 09:00"

    assert wants_appointment(text)
    assert extract_city(text) == "Bucaramanga"
    assert extract_start_iso(text) == "2026-07-10T09:00"
    assert procedure_for_text(text) == "tecnomecanica"
    assert wants_cancel_appointment("cancela mi cita 42")
    assert extract_appointment_id("cancela mi cita 42") == 42
    assert wants_reminder("recordame el 2026-07-10 09:00")
    assert extract_partner_decision("CONFIRMAR 123") == ("confirmar", 123)
    assert extract_partner_decision("rechazar #88") == ("rechazar", 88)
    assert extract_partner_decision("hola") is None


def test_procedure_maps_place_type_aliases() -> None:
    assert procedure_for_text("quiero agendar una cita en un cda") == "tecnomecanica"
    assert procedure_for_text("cda") == "tecnomecanica"
    assert procedure_for_text("centro de diagnostico automotriz") == "tecnomecanica"
    assert procedure_for_text("cita en un CIA") == "curso_multa"
    assert procedure_for_text("centro integral de atencion") == "curso_multa"
    assert procedure_for_text("cea") == "licencia_primera"
    assert procedure_for_text("escuela de conduccion") == "licencia_primera"
    assert procedure_for_text("curso de manejo") == "licencia_primera"
    assert procedure_for_text("crc") == "renovacion_licencia"
    assert procedure_for_text("reconocimiento de conductores") == "renovacion_licencia"
    assert procedure_for_text("curso de conduccion") == "licencia_primera"
    assert procedure_for_text("curso por multa") == "curso_multa"


def test_product_intent_extraction() -> None:
    assert wants_quote("cuanto cuesta el soat")
    assert wants_quote("cuanto vale una multa por semaforo en rojo")
    assert wants_payment("quiero pagar mi servicio")
    assert wants_handoff("quiero hablar con un asesor")
    assert not wants_handoff("ASESORAME")
    assert quote_service_for_text("cotizar seguro soat") == "soat"
    assert quote_service_for_text("cuanto vale una multa por semaforo en rojo") == "infraccion"
    assert extract_vehicle_type("SOAT moto 150 modelo 2020") == "moto"
    assert extract_displacement("SOAT moto 150 modelo 2020") == 150
    assert extract_model_year("SOAT moto 150 modelo 2020") == 2020
    assert extract_infraction_code("multa D04") == "D04"


def test_knowledge_intent_extraction() -> None:
    text = "que llevar para la tecnomecanica"

    assert wants_knowledge(text)
    assert knowledge_domain_for_text(text) == "tecnomecanica"
    assert knowledge_topic_for_text(text, domain="tecnomecanica") == "que_llevar"
    assert wants_city_coverage("hay cda para tecnomecanica en Bogota")
    assert not wants_knowledge("quiero consultar mis multas en simit cedula 123456789")


def test_general_traffic_and_situational_intents() -> None:
    assert wants_situational_advice("que pasa si me paro en rojo")
    assert wants_general_traffic_question("puedo circular con soat vencido en colombia")
    assert wants_general_traffic_question("que hago si tengo un accidente de transito")
    assert not wants_general_traffic_question("quiero pagar mi servicio")
    assert not wants_general_traffic_question("cuanto cuesta el soat")


def test_place_selection_extraction() -> None:
    places = [
        {"name": "CDA MOTOCICLETAS PARQUE CARACOLI", "city": "Floridablanca", "kind": "CDA", "distance_km": 0.81},
        {"name": "CDA VILLABEL", "city": "Bucaramanga", "kind": "CDA", "distance_km": 2.1},
    ]
    assert extract_place_selection("la segunda") == 2
    assert extract_place_selection("opcion 3") == 3
    assert extract_place_selection("esa me sirve") is None
    assert extract_place_selection("esa me sirve", places=places[:1]) == 1
    assert extract_place_selection("cda villabels", places=places) == 2
    assert extract_place_selection("cda", places=places) is None  # ambiguous kind-only
    assert extract_place_selection("el mas cercano", places=places) == 1
    assert wants_alternative_places("muestrame otras opciones")
    assert wants_place_comparison("cual es mejor? y por que?")
    assert format_place_comparison_response(places).lower().find("caracoli") >= 0


@pytest.mark.asyncio
async def test_place_comparison_and_name_correction_replaces_appointment(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    import bot_orchestrator.slices.run_turn.use_case as run_turn_module
    from bot_orchestrator.shared.appointment_selection import (
        PendingAppointmentSelection,
        appointment_selection_store,
    )
    from bot_orchestrator.slices.run_turn.schemas import AgentTurnRequest
    from bot_orchestrator.slices.run_turn.use_case import run_agent_turn

    monkeypatch.setattr(run_turn_module, "AppointmentClient", lambda: FakeAppointmentClient())
    monkeypatch.setattr(run_turn_module, "llm_provider_from_env", lambda: FakeLLMProvider())

    places = [
        {
            "id": "cda-caracoli",
            "name": "CDA MOTOCICLETAS PARQUE CARACOLI",
            "address": "CALLE 29",
            "city": "Floridablanca",
            "kind": "CDA",
            "distance_km": 0.81,
        },
        {
            "id": "cda-villabel",
            "name": "CDA VILLABEL",
            "address": "CARRERA 11",
            "city": "Bucaramanga",
            "kind": "CDA",
            "distance_km": 2.1,
        },
    ]
    appointment_selection_store.save(
        PendingAppointmentSelection(
            user_key="web-user",
            channel="web",
            procedure="tecnomecanica",
            places=places,
            starts_at="2026-07-11T10:00",
        )
    )

    compare = await run_agent_turn(
        AgentTurnRequest(user_key="web-user", channel="web", text="cual es mejor? y por que?")
    )
    assert compare.mode == "appointment_place_comparison"
    assert "cercania" in compare.text.lower() or "cerca" in compare.text.lower()
    assert "LLM" not in compare.text

    wrong = await run_agent_turn(
        AgentTurnRequest(user_key="web-user", channel="web", text="1")
    )
    assert wrong.mode == "appointment_created"
    assert FakeAppointmentClient.created[-1]["place"]["id"] == "cda-caracoli"

    fixed = await run_agent_turn(
        AgentTurnRequest(user_key="web-user", channel="web", text="cda villabels")
    )
    assert fixed.mode == "appointment_replaced"
    assert "appointment.cancel" in (fixed.tool_calls or [])
    assert FakeAppointmentClient.cancelled[-1]["appointment_id"] == FakeAppointmentClient.created[0]["id"]
    assert FakeAppointmentClient.created[-1]["place"]["id"] == "cda-villabel"
    assert "LLM" not in fixed.text


def test_format_soat_response() -> None:
    response = format_vigencia_response(
        {
            "placa": "ABC123",
            "vehiculo": {"marca": "Mazda", "linea": "2", "modelo": 2020},
            "soat": {"fechaVencimiento": "2026-10-15", "diasRestantes": 100},
        },
        intent="soat",
    )

    assert "15/10/2026" in response
    assert "SOAT" in response
    assert "Perfecto, si necesitas algo mas" not in response


def test_format_multas_response_without_multas() -> None:
    response = format_multas_response(
        {
            "tieneMultas": False,
            "simit": {"tieneMultas": False, "resumen": {"total": 0}},
            "local": {
                "city": "Bogota",
                "consulted": False,
                "portalUrl": "https://webfenix.movilidadbogota.gov.co/#/consulta-pagos",
            },
        }
    )

    assert "SIMIT" in response
    assert "no aparecen multas" in response.lower() or "No aparecen" in response or "no aparecen" in response
    assert "webfenix" in response


def test_format_multas_response_with_manizales_local() -> None:
    response = format_multas_response(
        {
            "simit": {
                "tieneMultas": True,
                "resumen": {"comparendos": 1, "multas": 1, "total": 250000},
            },
            "local": {
                "city": "Manizales",
                "consulted": True,
                "tieneMultas": True,
                "resumen": {"total": 180000},
                "portalUrl": "https://www.movilidadmanizales.com.co/portal-servicios/",
            },
        }
    )

    assert "SIMIT" in response
    assert "Manizales" in response
    assert "movilidadmanizales" in response


def test_format_multas_response_manizales_audiencia_zero_total() -> None:
    response = format_multas_response(
        {
            "simit": {"tieneMultas": False, "resumen": {"total": 0}},
            "local": {
                "city": "Manizales",
                "consulted": True,
                "tieneMultas": True,
                "resumen": {"total": 0, "comparendos": 1, "multas": 1},
                "detalles": [
                    {
                        "placa": "QLX871",
                        "codigo": "D04",
                        "infraccion": "D04 No detenerse ante una luz roja o amarilla de semaforo",
                        "fecha": "martes 19 de mayo 2026",
                        "tipo": "fotodeteccion",
                        "estado": "Audiencia",
                        "valor": "No aplica",
                    }
                ],
                "portalUrl": "https://www.movilidadmanizales.com.co/portal-servicios/",
            },
        }
    )

    assert "audiencia" in response.lower() or "registros" in response.lower()
    assert "D04" in response
    assert "QLX871" in response
    assert "luz roja" in response.lower() or "semaforo" in response.lower()
    assert "19 de mayo" in response.lower()
    assert "fotodeteccion" in response.lower()
    assert "no aplica" in response.lower()


def test_extract_city_supports_more_cities() -> None:
    assert extract_city("la multa fue en barranquilla") == "Barranquilla"
    assert extract_city("comparendo en Manizales") == "Manizales"
    assert extract_city("en santa marta") == "Santa Marta"


def test_format_runt_profile_response() -> None:
    response = format_runt_profile_response(
        {
            "ok": True,
            "documentoTail": "6789",
            "data": {
                "nombre": "Persona Demo",
                "estadoPersona": "ACTIVA",
                "estadoConductor": "ACTIVO",
                "licencias": [
                    {
                        "numero": "123456789",
                        "estado": "ACTIVA",
                        "categorias": [
                            {
                                "categoria": "B1",
                                "fechaExpedicion": "29/11/2024",
                                "fechaVencimiento": "29/11/2034",
                            },
                            {
                                "categoria": "A2",
                                "fechaExpedicion": "30/06/2026",
                                "fechaVencimiento": "30/06/2036",
                            },
                        ],
                    }
                ],
            },
        }
    )

    assert "6789" in response
    assert "B1" in response
    assert "vence 29/11/2034" in response
    assert "A2" in response
    assert "vence 30/06/2036" in response
    assert "123456789" not in response


def test_format_runt_profile_document_request() -> None:
    from bot_orchestrator.slices.run_turn.formatters import format_runt_profile_document_request

    text = format_runt_profile_document_request()
    assert "Claro, con gusto" in text
    assert "1234567890" in text
    assert "cedula" in text.lower()


def test_format_quote_response() -> None:
    response = format_quote_response(
        {
            "service_type": "soat",
            "price_min": 350000,
            "price_max": 1200000,
            "currency": "COP",
            "disclaimer": "Valor referencial.",
        }
    )
    assert "soat" in response
    assert "350000" in response


def test_notification_destination_only_for_whatsapp_phone_user_key() -> None:
    assert (
        notification_to_for_turn(
            AgentTurnRequest(user_key="+57 300 111 2233", text="agenda cita", channel="whatsapp")
        )
        == "573001112233"
    )
    assert notification_to_for_turn(AgentTurnRequest(user_key="web-user", text="agenda cita")) is None


def test_location_for_turn_accepts_colombia_metadata_only() -> None:
    assert location_for_turn(
        AgentTurnRequest(
            user_key="web-user",
            text="pin",
            metadata={"location_lat": 4.711, "location_lng": -74.0721},
        )
    ) == (4.711, -74.0721)
    assert location_for_turn(
        AgentTurnRequest(
            user_key="web-user",
            text="pin",
            metadata={"location_lat": 25.7617, "location_lng": -80.1918},
        )
    ) is None


def test_agent_response_default_mode_is_not_stub() -> None:
    assert AgentTurnResponse(text="menu").mode == "agent_menu"


@pytest.mark.asyncio
async def test_agent_uses_llm_provider_for_unknown_intent() -> None:
    response = await run_agent_turn(
        AgentTurnRequest(user_key="web-user", text="explicame que puedes hacer"),
        llm_provider=FakeLLMProvider(),
    )

    assert "respuesta LLM" in response.text
    assert response.mode in {"fake-llm", "knowledge_rag_llm", "llm_provider"}
    assert "llm.complete" in (response.tool_calls or [])


@pytest.mark.asyncio
async def test_agent_uses_quote_tool_before_llm(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(run_turn_module, "QuoteClient", lambda: FakeQuoteClient())

    response = await run_agent_turn(AgentTurnRequest(user_key="web-user", text="cuanto cuesta el SOAT"))

    assert response.mode == "quote_created"
    assert response.tool_calls == ["quote.create"]


@pytest.mark.asyncio
async def test_agent_routes_infraction_quote_to_quote_tool(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(run_turn_module, "QuoteClient", lambda: FakeQuoteClient())

    response = await run_agent_turn(
        AgentTurnRequest(user_key="web-user", text="cuanto vale una multa por semaforo en rojo")
    )

    assert response.mode == "infraccion_quote"
    assert response.tool_calls == ["quote.create"]
    assert "633.200" in response.text


@pytest.mark.asyncio
async def test_agent_uses_billing_tool_before_llm(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(run_turn_module, "BillingClient", lambda: FakeBillingClient())

    response = await run_agent_turn(AgentTurnRequest(user_key="web-user", text="quiero pagar"))

    assert response.mode == "payment_intent_created"
    assert response.tool_calls == ["billing.payment_intent.create"]


@pytest.mark.asyncio
async def test_agent_uses_handoff_tool_before_llm(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(run_turn_module, "HandoffClient", lambda: FakeHandoffClient())

    response = await run_agent_turn(AgentTurnRequest(user_key="web-user", text="quiero hablar con un asesor"))

    assert response.mode == "handoff_queued"
    assert response.tool_calls == ["handoff.create"]


@pytest.mark.asyncio
async def test_agent_cancels_appointment_before_llm(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(run_turn_module, "AppointmentClient", lambda: FakeAppointmentClient())

    response = await run_agent_turn(AgentTurnRequest(user_key="web-user", text="cancela mi cita 42"))

    assert response.mode == "appointment_cancelled"
    assert response.tool_calls == ["appointment.cancel"]
    assert "42" in response.text


@pytest.mark.asyncio
async def test_agent_schedules_manual_whatsapp_reminder(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(run_turn_module, "NotificationClient", lambda: FakeNotificationClient())

    response = await run_agent_turn(
        AgentTurnRequest(
            user_key="+57 300 111 2233",
            text="recordame revisar la tecnomecanica el 2026-07-10 09:00",
            channel="whatsapp",
        )
    )

    assert response.mode == "reminder_scheduled"
    assert response.tool_calls == ["notification.schedule"]
    assert "2026-07-10T09:00" in response.text


@pytest.mark.asyncio
async def test_agent_schedules_manual_whatsapp_reminder_with_natural_date(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(run_turn_module, "NotificationClient", lambda: FakeNotificationClient())

    response = await run_agent_turn(
        AgentTurnRequest(
            user_key="+57 300 111 2233",
            text="recordame revisar la tecnomecanica manana a las 10",
            channel="whatsapp",
        )
    )

    assert response.mode == "reminder_scheduled"
    assert response.tool_calls == ["notification.schedule"]


@pytest.mark.asyncio
async def test_agent_uses_runt_profile_tool_before_llm(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(run_turn_module, "VehicleClient", lambda: FakeVehicleClient())

    response = await run_agent_turn(
        AgentTurnRequest(user_key="web-user", text="consulta mi licencia cedula 123456789")
    )

    assert response.mode == "vehicle_runt_profile"
    assert response.tool_calls == ["vehicle.consult_runt_profile"]
    assert "B1" in response.text
    assert "vence 29/11/2034" in response.text


@pytest.mark.asyncio
async def test_agent_asks_cedula_for_runt_profile_with_standard_copy(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setattr(run_turn_module, "VehicleClient", lambda: FakeVehicleClient())

    response = await run_agent_turn(
        AgentTurnRequest(user_key="web-user", text="consulta mi licencia")
    )

    assert response.mode == "runt_profile_missing_document"
    assert "Claro, con gusto" in response.text
    assert "1234567890" in response.text

    follow_up = await run_agent_turn(
        AgentTurnRequest(user_key="web-user", text="1234567890")
    )
    assert follow_up.mode == "vehicle_runt_profile"
    assert "vence 29/11/2034" in follow_up.text


@pytest.mark.asyncio
async def test_agent_requires_explicit_place_selection_when_multiple_places(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(run_turn_module, "PlacesClient", lambda: FakePlacesClient())
    monkeypatch.setattr(run_turn_module, "AppointmentClient", lambda: FakeAppointmentClient())

    first = await run_agent_turn(
        AgentTurnRequest(
            user_key="web-user",
            text="quiero agendar tecnomecanica en Bogota el 2026-07-10 09:00",
        )
    )

    assert first.mode == "appointment_place_selection_required"
    assert first.tool_calls == ["places.find_nearest"]
    assert "CDA Uno" in first.text
    assert "CDA Dos" in first.text
    assert FakeAppointmentClient.created == []

    second = await run_agent_turn(AgentTurnRequest(user_key="web-user", text="la segunda"))

    assert second.mode == "appointment_created"
    assert second.tool_calls == [
        "appointment.select_place",
        "appointment.create",
        "notification.partner_notify",
    ]
    assert FakeAppointmentClient.created[0]["place"]["id"] == "cda-2"
    assert "CDA Dos" in second.text
    assert "solicite la cita" in second.text.lower() or "afiliado" in second.text.lower()


@pytest.mark.asyncio
async def test_agent_uses_whatsapp_location_metadata_without_city(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(run_turn_module, "PlacesClient", lambda: FakePlacesClient())

    response = await run_agent_turn(
        AgentTurnRequest(
            user_key="573001112233",
            text="quiero agendar tecnomecanica el 2026-07-10 09:00",
            channel="whatsapp",
            metadata={"location_lat": 4.711, "location_lng": -74.0721},
        )
    )

    assert response.mode == "appointment_place_selection_required"
    assert response.tool_calls == ["places.find_nearest"]
    assert FakePlacesClient.calls[0]["city"] is None
    assert FakePlacesClient.calls[0]["lat"] == 4.711
    assert FakePlacesClient.calls[0]["lng"] == -74.0721


@pytest.mark.asyncio
async def test_agent_confirms_single_place_with_natural_date(monkeypatch: pytest.MonkeyPatch) -> None:
    class SinglePlaceClient(FakePlacesClient):
        async def find_nearest(
            self,
            *,
            procedure: str,
            city: str | None = None,
            lat: float | None = None,
            lng: float | None = None,
        ) -> dict[str, object]:
            self.calls.append({"procedure": procedure, "city": city, "lat": lat, "lng": lng})
            return {
                "places": [
                    {
                        "id": "cda-unico",
                        "name": "CDA Canaveral",
                        "address": "Diagonal 31 #29-153 Local 2",
                        "city": "Floridablanca",
                        "department": "Santander",
                        "kind": "CDA",
                        "distance_km": 0.516,
                    }
                ]
            }

    monkeypatch.setattr(run_turn_module, "PlacesClient", lambda: SinglePlaceClient())
    monkeypatch.setattr(run_turn_module, "AppointmentClient", lambda: FakeAppointmentClient())

    first = await run_agent_turn(
        AgentTurnRequest(
            user_key="+573001112233",
            text="quiero agendar tecnomecanica",
            channel="whatsapp",
            metadata={"location_lat": 7.11, "location_lng": -73.11},
        )
    )
    second = await run_agent_turn(
        AgentTurnRequest(user_key="+573001112233", text="dale, me sirve, manana a las 10", channel="whatsapp")
    )

    assert first.mode == "places_suggested"
    assert "516 m aprox. (linea recta)" in first.text
    assert "afiliado" in first.text.lower()
    assert second.mode == "appointment_created"
    assert FakeAppointmentClient.created[0]["place"]["id"] == "cda-unico"


@pytest.mark.asyncio
async def test_agent_handles_partner_confirm_command(monkeypatch: pytest.MonkeyPatch) -> None:
    FakeAppointmentClient.decisions.clear()
    monkeypatch.setattr(run_turn_module, "AppointmentClient", lambda: FakeAppointmentClient())

    response = await run_agent_turn(
        AgentTurnRequest(user_key="573009998877", text="CONFIRMAR 88", channel="whatsapp")
    )

    assert response.mode == "appointment_partner_confirmed"
    assert response.tool_calls == ["appointment.confirm"]
    assert "confirmada" in response.text.lower()
    assert FakeAppointmentClient.decisions == [{"action": "confirm", "appointment_id": 88}]


@pytest.mark.asyncio
async def test_agent_resumes_pending_appointment_when_location_arrives(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(run_turn_module, "PlacesClient", lambda: FakePlacesClient())

    first = await run_agent_turn(
        AgentTurnRequest(
            user_key="573001112233",
            text="quiero agendar tecnomecanica el 2026-07-10 09:00",
            channel="whatsapp",
        )
    )
    second = await run_agent_turn(
        AgentTurnRequest(
            user_key="573001112233",
            text="Acabo de compartir mi ubicacion actual por WhatsApp.",
            channel="whatsapp",
            metadata={"geo_lat": 4.711, "geo_lng": -74.0721},
        )
    )

    assert first.mode == "appointment_missing_location"
    assert second.mode == "appointment_place_selection_required"
    assert FakePlacesClient.calls[0]["lat"] == 4.711
    assert FakePlacesClient.calls[0]["lng"] == -74.0721


@pytest.mark.asyncio
async def test_agent_resumes_pending_vehicle_consult_and_quotes_tecno(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(run_turn_module, "VehicleClient", lambda: FakeVehicleClient())
    monkeypatch.setattr(run_turn_module, "QuoteClient", lambda: FakeQuoteClient())

    first = await run_agent_turn(AgentTurnRequest(user_key="web-user", text="necesito la tecno"))
    second = await run_agent_turn(AgentTurnRequest(user_key="web-user", text="ABC123 1096065250"))

    assert first.mode == "vehicle_missing_data"
    assert first.text.startswith("Claro, con gusto.")
    assert "ABC123 1234567890" in first.text
    assert second.mode == "vehicle_tecnomecanica"
    assert second.tool_calls == ["vehicle.check_vigencia", "quote.create"]
    assert "vencida" in second.text.lower()
    assert "368.853" in second.text
    assert FakeQuoteClient.calls[0]["service_type"] == "tecnomecanica"
    assert FakeQuoteClient.calls[0]["categoria"] == "carro"


@pytest.mark.asyncio
async def test_agent_accumulates_plate_and_document_across_turns(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(run_turn_module, "VehicleClient", lambda: FakeVehicleClient())
    monkeypatch.setattr(run_turn_module, "QuoteClient", lambda: FakeQuoteClient())

    first = await run_agent_turn(AgentTurnRequest(user_key="web-user", text="necesito la tecno"))
    second = await run_agent_turn(AgentTurnRequest(user_key="web-user", text="ABC123"))
    third = await run_agent_turn(AgentTurnRequest(user_key="web-user", text="1096065250"))

    assert first.mode == "vehicle_missing_data"
    assert second.mode == "vehicle_missing_data"
    assert second.text.startswith("Claro, con gusto.")
    assert "1234567890" in second.text
    assert "ABC123" not in second.text
    assert third.mode == "vehicle_tecnomecanica"
    assert third.tool_calls == ["vehicle.check_vigencia", "quote.create"]


@pytest.mark.asyncio
async def test_agent_asks_intent_when_plate_and_document_arrive_without_keyword(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setattr(run_turn_module, "VehicleClient", lambda: FakeVehicleClient())
    monkeypatch.setattr(run_turn_module, "QuoteClient", lambda: FakeQuoteClient())

    first = await run_agent_turn(AgentTurnRequest(user_key="web-user", text="FSO879 79837308"))
    second = await run_agent_turn(AgentTurnRequest(user_key="web-user", text="revisar su tecno"))

    assert first.mode == "vehicle_missing_intent"
    assert "FSO879" in first.text
    assert "79837308" in first.text
    assert second.mode == "vehicle_tecnomecanica"
    assert second.tool_calls == ["vehicle.check_vigencia", "quote.create"]


@pytest.mark.asyncio
async def test_agent_quotes_soat_without_creating_license_appointment_context(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(run_turn_module, "VehicleClient", lambda: FakeVehicleClient())
    monkeypatch.setattr(run_turn_module, "QuoteClient", lambda: FakeQuoteClient())

    response = await run_agent_turn(
        AgentTurnRequest(user_key="web-user", text="revisar soat placa ABC123 cedula 1096065250")
    )

    assert response.mode == "vehicle_soat"
    assert response.tool_calls == ["vehicle.check_vigencia", "quote.create"]
    assert FakeQuoteClient.calls[0]["service_type"] == "soat"
    assert appointment_selection_store.get(user_key="web-user", channel="web") is None


@pytest.mark.asyncio
async def test_agent_reuses_last_vehicle_slots_for_soat_typo_followup(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setattr(run_turn_module, "VehicleClient", lambda: FakeVehicleClient())
    monkeypatch.setattr(run_turn_module, "QuoteClient", lambda: FakeQuoteClient())
    monkeypatch.setattr(run_turn_module, "llm_provider_from_env", lambda: FakeLLMProvider())

    first = await run_agent_turn(
        AgentTurnRequest(user_key="web-user", text="revisar tecno placa FSO879 cedula 79837308")
    )
    second = await run_agent_turn(AgentTurnRequest(user_key="web-user", text="y su soart"))

    assert first.mode == "vehicle_tecnomecanica"
    assert second.mode == "vehicle_soat"
    assert second.tool_calls == ["vehicle.check_vigencia", "quote.create"]
    assert FakeQuoteClient.calls[-1]["service_type"] == "soat"
    assert "LLM" not in second.text


@pytest.mark.asyncio
async def test_agent_asks_again_for_soat_when_no_slots_no_llm(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setattr(run_turn_module, "llm_provider_from_env", lambda: FakeLLMProvider())

    response = await run_agent_turn(AgentTurnRequest(user_key="web-user", text="y su soart"))

    assert response.mode == "vehicle_missing_data"
    assert response.text.startswith("Claro, con gusto.")
    assert "ABC123 1234567890" in response.text
    assert "LLM" not in response.text


@pytest.mark.asyncio
async def test_agent_uses_knowledge_tool_before_llm(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(run_turn_module, "KnowledgeClient", lambda: FakeKnowledgeClient())

    response = await run_agent_turn(AgentTurnRequest(user_key="web-user", text="que llevar para la tecnomecanica"))

    assert response.mode == "knowledge_info"
    assert response.tool_calls == ["knowledge.get_info"]
    assert "SOAT vigente" in response.text


@pytest.mark.asyncio
async def test_agent_uses_city_knowledge_tool_before_appointment(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(run_turn_module, "KnowledgeClient", lambda: FakeKnowledgeClient())

    response = await run_agent_turn(
        AgentTurnRequest(user_key="web-user", text="hay cda para tecnomecanica en Bogota")
    )

    assert response.mode == "knowledge_city"
    assert response.tool_calls == ["knowledge.city_info"]
    assert "Bogota" in response.text


def test_agent_internal_status_requires_token(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("INTERNAL_SERVICE_TOKEN", "internal-test-token")
    client = TestClient(app)

    assert client.get("/internal/status").status_code == 401

    response = client.get(
        "/internal/status",
        headers={"Authorization": "Bearer internal-test-token"},
    )
    assert response.status_code == 200
    assert response.json()["service"] == "bot-orchestrator"


def test_system_prompt_loader_builds_ordered_prompt() -> None:
    prompt = build_system_prompt()

    assert "<!-- identity.md -->" in prompt
    assert "<!-- flows/agenda.md -->" in prompt
    assert "Eres *Civi*" in prompt or "Eres Civi" in prompt
    assert "tools" in prompt.lower()


def test_prompt_loader_rejects_missing_part() -> None:
    with pytest.raises(FileNotFoundError):
        load_prompt_part("flows/no-existe.md")


def test_llm_provider_mode_fails_closed(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("LLM_PROVIDER_MODE", "unknown-provider")

    with pytest.raises(RuntimeError, match="unsupported LLM provider mode"):
        llm_provider_from_env()


def test_openai_llm_provider_requires_credentials() -> None:
    with pytest.raises(RuntimeError, match="OPENAI_API_KEY"):
        OpenAIResponsesLLMProvider(api_key="", model="")


def test_deepseek_llm_provider_requires_credentials() -> None:
    with pytest.raises(RuntimeError, match="DEEPSEEK"):
        OpenAICompatibleChatLLMProvider(
            provider_mode="deepseek",
            api_key="",
            model="deepseek-chat",
            base_url="https://api.deepseek.com/v1",
        )


@pytest.mark.asyncio
async def test_openai_llm_provider_sends_responses_payload_without_live_call() -> None:
    requests: list[httpx.Request] = []

    async def handler(request: httpx.Request) -> httpx.Response:
        requests.append(request)
        return httpx.Response(
            200,
            json={
                "id": "resp_test",
                "output_text": "Respuesta desde OpenAI",
            },
        )

    provider = OpenAIResponsesLLMProvider(
        api_key="token-test",
        model="gpt-test",
        base_url="https://api.example.test",
        transport=httpx.MockTransport(handler),
    )

    result = await provider.complete(
        system_prompt="Eres Civi.",
        user_text="hola",
        user_key="user-1",
        channel="web",
    )

    assert result == {
        "provider_mode": "openai-responses",
        "text": "Respuesta desde OpenAI",
        "response_id": "resp_test",
    }
    assert str(requests[0].url) == "https://api.example.test/v1/responses"
    assert requests[0].headers["Authorization"] == "Bearer token-test"
    sent_payload = json.loads(requests[0].read().decode("utf-8"))
    assert sent_payload["model"] == "gpt-test"
    assert sent_payload["instructions"] == "Eres Civi."
    assert sent_payload["input"] == "hola"
    assert sent_payload["store"] is False
    assert sent_payload["metadata"] == {"service": "bot-orchestrator", "channel": "web"}


@pytest.mark.asyncio
async def test_openai_compatible_chat_provider_sends_chat_completion_without_live_call() -> None:
    requests: list[httpx.Request] = []

    async def handler(request: httpx.Request) -> httpx.Response:
        requests.append(request)
        return httpx.Response(
            200,
            json={
                "id": "chatcmpl_test",
                "choices": [{"message": {"content": "Respuesta desde DeepSeek"}}],
            },
        )

    provider = OpenAICompatibleChatLLMProvider(
        provider_mode="deepseek",
        api_key="token-test",
        model="deepseek-chat",
        base_url="https://api.deepseek.test/v1",
        transport=httpx.MockTransport(handler),
    )

    result = await provider.complete(
        system_prompt="Eres Civi.",
        user_text="hola",
        user_key="user-1",
        channel="web",
    )

    assert result == {
        "provider_mode": "deepseek",
        "text": "Respuesta desde DeepSeek",
        "response_id": "chatcmpl_test",
    }
    assert str(requests[0].url) == "https://api.deepseek.test/v1/chat/completions"
    assert requests[0].headers["Authorization"] == "Bearer token-test"
    sent_payload = json.loads(requests[0].read().decode("utf-8"))
    assert sent_payload["model"] == "deepseek-chat"
    assert sent_payload["messages"] == [
        {"role": "system", "content": "Eres Civi."},
        {"role": "user", "content": "hola"},
    ]


def test_provider_env_name_selects_deepseek(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.delenv("LLM_PROVIDER_MODE", raising=False)
    monkeypatch.setenv("LLM_PROVIDER", "deepseek")
    monkeypatch.setenv("DEEPSEEK_API_KEY", "token-test")
    monkeypatch.setenv("DEEPSEEK_MODEL", "deepseek-chat")

    provider = llm_provider_from_env()

    assert isinstance(provider, OpenAICompatibleChatLLMProvider)


@pytest.mark.asyncio
async def test_appointment_cda_skips_procedure_question(monkeypatch: pytest.MonkeyPatch) -> None:
    import bot_orchestrator.slices.run_turn.use_case as run_turn_module
    from bot_orchestrator.slices.run_turn.schemas import AgentTurnRequest
    from bot_orchestrator.slices.run_turn.use_case import run_agent_turn

    monkeypatch.setattr(run_turn_module, "PlacesClient", lambda: FakePlacesClient())

    first = await run_agent_turn(
        AgentTurnRequest(user_key="web-user", channel="web", text="quiero agendar una cita en un cda")
    )
    assert first.mode == "appointment_missing_location"

    second = await run_agent_turn(
        AgentTurnRequest(user_key="web-user", channel="web", text="cda")
    )
    # Soft pending already has tecnomecanica; bare "cda" should not re-ask procedure.
    assert second.mode == "appointment_missing_location"


@pytest.mark.asyncio
async def test_appointment_crc_maps_to_renovacion(monkeypatch: pytest.MonkeyPatch) -> None:
    import bot_orchestrator.slices.run_turn.use_case as run_turn_module
    from bot_orchestrator.slices.run_turn.schemas import AgentTurnRequest
    from bot_orchestrator.slices.run_turn.use_case import run_agent_turn

    monkeypatch.setattr(run_turn_module, "PlacesClient", lambda: FakePlacesClient())

    first = await run_agent_turn(
        AgentTurnRequest(user_key="web-user", channel="web", text="agendame un CRC")
    )
    assert first.mode == "appointment_missing_location"

    second = await run_agent_turn(
        AgentTurnRequest(user_key="web-user", channel="web", text="bucaramanga")
    )
    assert second.tool_calls == ["places.find_nearest"]
    assert FakePlacesClient.calls[-1]["procedure"] == "renovacion_licencia"
    assert FakePlacesClient.calls[-1]["city"] == "Bucaramanga"


@pytest.mark.asyncio
async def test_appointment_curso_with_crc_mention_warns_cia(monkeypatch: pytest.MonkeyPatch) -> None:
    import bot_orchestrator.slices.run_turn.use_case as run_turn_module
    from bot_orchestrator.slices.run_turn.schemas import AgentTurnRequest
    from bot_orchestrator.slices.run_turn.use_case import run_agent_turn

    monkeypatch.setattr(run_turn_module, "PlacesClient", lambda: FakePlacesClient())

    first = await run_agent_turn(
        AgentTurnRequest(
            user_key="web-user",
            channel="web",
            text="quiero agendar curso por multa pero me dijeron CRC",
        )
    )
    assert first.mode == "appointment_missing_location"
    assert "CIA" in first.text
    assert "CRC" in first.text


@pytest.mark.asyncio
async def test_multas_asks_city_then_query_then_consults(monkeypatch: pytest.MonkeyPatch) -> None:
    import bot_orchestrator.slices.run_turn.use_case as run_turn_module
    from bot_orchestrator.slices.run_turn.schemas import AgentTurnRequest
    from bot_orchestrator.slices.run_turn.use_case import run_agent_turn

    monkeypatch.setattr(run_turn_module, "VehicleClient", lambda: FakeVehicleClient())
    monkeypatch.setattr(run_turn_module, "llm_provider_from_env", lambda: FakeLLMProvider())

    first = await run_agent_turn(
        AgentTurnRequest(user_key="web-user", channel="web", text="puedes mirar mis multas")
    )
    assert first.mode == "multas_missing_city"
    assert first.text == format_multas_city_request()

    second = await run_agent_turn(
        AgentTurnRequest(user_key="web-user", channel="web", text="Manizales")
    )
    assert second.mode == "multas_missing_document"
    assert second.text == format_multas_query_request(ciudad="Manizales")

    third = await run_agent_turn(
        AgentTurnRequest(user_key="web-user", channel="web", text="1096065250")
    )
    assert third.mode == "vehicle_multas"
    assert third.tool_calls == ["vehicle.consult_multas"]


@pytest.mark.asyncio
async def test_multas_nacional_accepts_plate_and_correction_without_llm(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    import bot_orchestrator.slices.run_turn.use_case as run_turn_module
    from bot_orchestrator.slices.run_turn.schemas import AgentTurnRequest
    from bot_orchestrator.slices.run_turn.use_case import run_agent_turn

    calls: list[dict[str, object]] = []

    class TrackingVehicleClient(FakeVehicleClient):
        async def consult_multas(self, *, documento: str, ciudad: str | None = None) -> dict[str, object]:
            calls.append({"documento": documento, "ciudad": ciudad})
            return await super().consult_multas(documento=documento, ciudad=ciudad)

    monkeypatch.setattr(run_turn_module, "VehicleClient", TrackingVehicleClient)
    monkeypatch.setattr(run_turn_module, "llm_provider_from_env", lambda: FakeLLMProvider())

    first = await run_agent_turn(
        AgentTurnRequest(user_key="web-user", channel="web", text="quiero ver mis multas")
    )
    assert first.mode == "multas_missing_city"

    second = await run_agent_turn(
        AgentTurnRequest(user_key="web-user", channel="web", text="no se, mira general")
    )
    assert second.mode == "multas_missing_document"
    assert "ABC123 o 1234567890" in second.text

    third = await run_agent_turn(
        AgentTurnRequest(user_key="web-user", channel="web", text="ABC123")
    )
    assert third.mode == "vehicle_multas"
    assert calls[-1]["documento"] == "ABC123"
    assert calls[-1]["ciudad"] is None

    fourth = await run_agent_turn(
        AgentTurnRequest(user_key="web-user", channel="web", text="30328991 y esa")
    )
    assert fourth.mode == "vehicle_multas"
    assert calls[-1]["documento"] == "30328991"
    assert "LLM" not in fourth.text


@pytest.mark.asyncio
async def test_exosto_and_escape_hit_catalog(monkeypatch: pytest.MonkeyPatch) -> None:
    import bot_orchestrator.slices.run_turn.use_case as run_turn_module
    from bot_orchestrator.slices.run_turn.schemas import AgentTurnRequest
    from bot_orchestrator.slices.run_turn.use_case import run_agent_turn

    monkeypatch.setattr(run_turn_module, "QuoteClient", lambda: FakeQuoteClient())

    exosto = await run_agent_turn(
        AgentTurnRequest(
            user_key="web-user",
            channel="web",
            text="TENGO EL EXOSTO MODIFICADO Y ESO ES ILEGAL",
        )
    )
    assert exosto.mode == "infraccion_quote"
    assert "D17" in exosto.text

    typo = await run_agent_turn(
        AgentTurnRequest(user_key="web-user", channel="web", text="tengo el exsosto mmoficiado")
    )
    assert typo.mode == "infraccion_quote"
    assert "D17" in typo.text
    assert "exosto" in str(FakeQuoteClient.calls[-1].get("consulta", "")).lower()

    escape = await run_agent_turn(
        AgentTurnRequest(user_key="web-user", channel="web", text="NOOOO ME ESCAPE")
    )
    assert escape.mode == "infraccion_quote"
    assert "C31" in escape.text
    assert "D04" not in escape.text


@pytest.mark.asyncio
async def test_asesorame_does_not_handoff(monkeypatch: pytest.MonkeyPatch) -> None:
    import bot_orchestrator.slices.run_turn.use_case as run_turn_module
    from bot_orchestrator.slices.run_turn.schemas import AgentTurnRequest
    from bot_orchestrator.slices.run_turn.use_case import run_agent_turn

    class TrackingHandoff(FakeHandoffClient):
        calls = 0

        async def create(self, *, user_key: str, reason: str, channel: str) -> dict[str, object]:
            TrackingHandoff.calls += 1
            return await super().create(user_key=user_key, reason=reason, channel=channel)

    monkeypatch.setattr(run_turn_module, "HandoffClient", TrackingHandoff)
    monkeypatch.setattr(
        run_turn_module,
        "llm_provider_from_env",
        lambda: type(
            "P",
            (),
            {
                "complete": staticmethod(
                    lambda **_: __import__("asyncio").sleep(0, result={"text": "Te oriento yo.", "provider_mode": "test"})
                )
            },
        )(),
    )

    # Simpler: patch _run_llm_fallback path via knowledge - ASESORAME may hit situational/LLM
    async def fake_complete(**kwargs):  # type: ignore[no-untyped-def]
        return {"text": "Te oriento yo mismo.", "provider_mode": "test"}

    class FakeLLM:
        async def complete(self, **kwargs):  # type: ignore[no-untyped-def]
            return await fake_complete(**kwargs)

    monkeypatch.setattr(run_turn_module, "llm_provider_from_env", lambda: FakeLLM())
    TrackingHandoff.calls = 0
    response = await run_agent_turn(
        AgentTurnRequest(user_key="web-user", channel="web", text="ASESORAME")
    )
    assert response.mode != "handoff_queued"
    assert TrackingHandoff.calls == 0


def test_history_from_recent_turns_builds_role_pairs() -> None:
    from bot_orchestrator.adapters.outbound.llm_provider import history_from_recent_turns

    history = history_from_recent_turns(
        [
            {"user_text": "hola", "agent_text": "Hola, soy Civi"},
            {"user_text": "cuanto vale C02", "agent_text": "C02 vale..."},
        ]
    )
    assert history == [
        {"role": "user", "content": "hola"},
        {"role": "assistant", "content": "Hola, soy Civi"},
        {"role": "user", "content": "cuanto vale C02"},
        {"role": "assistant", "content": "C02 vale..."},
    ]


@pytest.mark.asyncio
async def test_llm_fallback_passes_recent_turn_history(monkeypatch: pytest.MonkeyPatch) -> None:
    FakeLLMProvider.last_history = None
    monkeypatch.setattr(run_turn_module, "VehicleClient", FakeVehicleClient)
    monkeypatch.setattr(run_turn_module, "PlacesClient", FakePlacesClient)
    monkeypatch.setattr(run_turn_module, "AppointmentClient", FakeAppointmentClient)
    monkeypatch.setattr(run_turn_module, "QuoteClient", FakeQuoteClient)
    monkeypatch.setattr(run_turn_module, "KnowledgeClient", FakeKnowledgeClient)
    monkeypatch.setattr(run_turn_module, "NotificationClient", FakeNotificationClient)
    monkeypatch.setattr(run_turn_module, "HandoffClient", FakeHandoffClient)
    monkeypatch.setattr(run_turn_module, "BillingClient", FakeBillingClient)

    response = await run_agent_turn(
        AgentTurnRequest(
            user_key="web-user",
            text="explicame otra vez",
            metadata={
                "recent_turns": [
                    {"user_text": "hola", "agent_text": "Hola, soy Civi"},
                    {"user_text": "que es SOAT", "agent_text": "El SOAT cubre..."},
                ]
            },
        ),
        llm_provider=FakeLLMProvider(),
    )
    assert "explicame otra vez" in response.text
    assert FakeLLMProvider.last_history is not None
    assert FakeLLMProvider.last_history[0]["content"] == "hola"
    assert FakeLLMProvider.last_history[-1]["content"] == "El SOAT cubre..."

