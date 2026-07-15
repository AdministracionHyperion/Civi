from __future__ import annotations

import logging
import os
import re
import unicodedata

import httpx
from civi_common import is_colombia_latlng

from bot_orchestrator.adapters.outbound.appointment_client import AppointmentClient
from bot_orchestrator.adapters.outbound.billing_client import BillingClient
from bot_orchestrator.adapters.outbound.handoff_client import HandoffClient
from bot_orchestrator.adapters.outbound.knowledge_client import KnowledgeClient
from bot_orchestrator.adapters.outbound.llm_provider import (
    LLMProvider,
    history_from_recent_turns,
    llm_provider_from_env,
)
from bot_orchestrator.adapters.outbound.notification_client import NotificationClient
from bot_orchestrator.adapters.outbound.places_client import PlacesClient
from bot_orchestrator.adapters.outbound.quote_client import QuoteClient
from bot_orchestrator.adapters.outbound.vehicle_client import VehicleClient
from bot_orchestrator.prompts.loader import build_system_prompt
from bot_orchestrator.shared.appointment_selection import (
    AWAITING_PROCEDURE,
    LastVehicleSlots,
    PendingAppointmentSelection,
    PendingVehicleConsult,
    appointment_selection_store,
    last_vehicle_slots_store,
    shared_pending_store,
    vehicle_consult_store,
)
from bot_orchestrator.shared.consult_jobs import (
    ConsultJob,
    ConsultJobStatus,
    get_consult_job_repository,
    estimated_wait_seconds,
    generate_job_id,
)
from bot_orchestrator.shared.date_parser import parse_natural_datetime
from bot_orchestrator.shared.vehicle_category import map_clase_to_quote_category

from .extractors import (
    _has_datetime_hint,
    extract_city,
    extract_appointment_id,
    extract_document,
    extract_displacement,
    extract_infraction_code,
    extract_model_year,
    extract_partner_decision,
    extract_place_selection,
    extract_plate,
    extract_start_iso,
    extract_vehicle_type,
    knowledge_domain_for_text,
    knowledge_topic_for_text,
    mentions_crc,
    normalize_infraccion_query,
    procedure_for_text,
    quote_service_for_text,
    wants_abandon_appointment_flow,
    wants_appointment,
    wants_cancel_appointment,
    wants_city_coverage,
    wants_alternative_places,
    wants_general_multas_city,
    wants_handoff,
    wants_knowledge,
    wants_multas,
    wants_nearest_place,
    wants_payment,
    wants_place_comparison,
    wants_quote,
    wants_reminder,
    wants_runt_profile,
    wants_situational_advice,
    wants_general_traffic_question,
    wants_infraccion_lookup,
    wants_soat,
    wants_soat_info,
    wants_accident_info,
    wants_infraccion_explanation,
    wants_tecno,
    wants_vigencia,
    wants_both_vigencias,
    wants_other_vehicle,
    wants_same_vehicle_slots,
    is_pure_greeting,
    is_soft_conversation_close,
    wants_fresh_consult,
)
from .formatters import (
    CONVERSATION_CLOSED_TEXT,
    format_appointment_response,
    format_appointments_list,
    format_cancel_appointment_response,
    format_city_knowledge_response,
    format_informative_places_response,
    format_knowledge_response,
    format_multas_response,
    format_no_affiliate_coverage,
    format_partner_decision_response,
    format_pending_place_date_request,
    format_place_comparison_response,
    format_place_response,
    format_place_options_response,
    format_payment_intent_response,
    format_quote_response,
    format_reminder_response,
    format_runt_profile_document_request,
    format_runt_profile_response,
    format_handoff_response,
    format_infraccion_detail_response,
    format_multas_city_request,
    format_multas_query_request,
    format_vehicle_slots_request,
    format_vigencia_response,
    soat_needs_quote,
    tecno_needs_quote,
)
from .schemas import AgentTurnRequest, AgentTurnResponse

logger = logging.getLogger(__name__)

PHONE_USER_KEY_RE = re.compile(r"^\+?[0-9]{10,15}$")


def _clear_channel_session(*, user_key: str, channel: str) -> None:
    """Drop in-memory consult/appointment state for this WhatsApp/web channel."""
    vehicle_consult_store.clear(user_key=user_key, channel=channel)
    last_vehicle_slots_store.clear(user_key=user_key, channel=channel)
    appointment_selection_store.clear(user_key=user_key, channel=channel)
    shared_pending_store.clear(user_key=user_key)


async def run_agent_turn(
    payload: AgentTurnRequest,
    *,
    llm_provider: LLMProvider | None = None,
) -> AgentTurnResponse:
    control = str((payload.metadata or {}).get("control") or "").strip().lower()
    if control in {"hard_reset", "soft_reset"}:
        _clear_channel_session(user_key=payload.user_key, channel=payload.channel)
        return AgentTurnResponse(
            text="session_cleared",
            state_version=0,
            mode="session_cleared",
        )

    text = payload.text
    fresh_placa = extract_plate(text)
    fresh_documento = extract_document(text)
    placa = fresh_placa
    documento = fresh_documento

    # Persist WhatsApp/GPS pin across turns before any appointment branching.
    _capture_turn_location(payload)

    lowered = text.lower()
    partner_response = await _maybe_handle_partner_decision(payload)
    if partner_response is not None:
        return partner_response

    if wants_cancel_appointment(text):
        appointment_id = extract_appointment_id(text)
        if appointment_id is None:
            return AgentTurnResponse(
                text="Claro. Pasame el ID de la cita que quieres cancelar. Si no lo tienes, pregunta por tus citas y te ayudo.",
                state_version=1,
                mode="appointment_cancel_missing_id",
            )
        try:
            data = await AppointmentClient().cancel(user_key=payload.user_key, appointment_id=appointment_id)
            return AgentTurnResponse(
                text=format_cancel_appointment_response(data),
                state_version=1,
                mode="appointment_cancelled" if data.get("success") else "appointment_cancel_not_found",
                tool_calls=["appointment.cancel"],
            )
        except httpx.HTTPStatusError:
            return AgentTurnResponse(
                text="Uy, no pude cancelar la cita. Intentemoslo de nuevo en un momento.",
                state_version=1,
                mode="appointment_cancel_error",
            )

    if (
        ("mis citas" in lowered or "mi cita" in lowered or "cuando es mi cita" in lowered)
        and not wants_appointment(text)
        and not wants_cancel_appointment(text)
    ):
        try:
            data = await AppointmentClient().list_for_user(user_key=payload.user_key)
            return AgentTurnResponse(
                text=format_appointments_list(data),
                state_version=1,
                mode="appointments_list",
                tool_calls=["appointment.list"],
            )
        except httpx.HTTPStatusError:
            return AgentTurnResponse(
                text="Uy, no pude revisar tus citas. Intentemoslo de nuevo en un momento.",
                state_version=1,
                mode="appointments_error",
            )

    if wants_reminder(text):
        remind_at = _parse_appointment_datetime(text)
        notification_to = notification_to_for_turn(payload)
        if not remind_at:
            return AgentTurnResponse(
                text="Claro. Dime la fecha y hora del recordatorio, por ejemplo manana a las 10 o 2026-07-10 09:00.",
                state_version=1,
                mode="reminder_missing_date",
            )
        if not notification_to:
            return AgentTurnResponse(
                text="Con gusto lo programo cuando el canal tenga un numero WhatsApp valido.",
                state_version=1,
                mode="reminder_missing_destination",
            )
        try:
            data = await NotificationClient().schedule_reminder(
                user_key=payload.user_key,
                to=notification_to,
                body=f"Recordatorio Civi: {text[:240]}",
                remind_at=remind_at,
            )
            return AgentTurnResponse(
                text=format_reminder_response(data),
                state_version=1,
                mode="reminder_scheduled",
                tool_calls=["notification.schedule"],
            )
        except httpx.HTTPStatusError:
            return AgentTurnResponse(
                text="Uy, no pude programar el recordatorio. Intentemoslo de nuevo en un momento.",
                state_version=1,
                mode="reminder_error",
            )

    if wants_handoff(text):
        try:
            data = await HandoffClient().create(user_key=payload.user_key, reason=text[:240], channel=payload.channel)
            return AgentTurnResponse(
                text=format_handoff_response(data),
                state_version=1,
                mode="handoff_queued",
                tool_calls=["handoff.create"],
            )
        except httpx.HTTPStatusError:
            return AgentTurnResponse(
                text="Uy, no pude crear el caso para un asesor. Intentemoslo de nuevo en un momento.",
                state_version=1,
                mode="handoff_error",
            )

    if wants_infraccion_lookup(text):
        try:
            consulta = normalize_infraccion_query(text)
            data = await QuoteClient().create(
                service_type="infraccion",
                consulta=consulta,
                codigo=extract_infraction_code(text),
            )
            return AgentTurnResponse(
                text=format_quote_response(data),
                state_version=1,
                mode="infraccion_quote",
                tool_calls=["quote.create"],
            )
        except httpx.HTTPStatusError:
            pass
        except Exception:
            logger.exception("Failed infraccion catalog lookup")

    if wants_situational_advice(text) or wants_general_traffic_question(text):
        return await _answer_with_knowledge_context(payload, llm_provider=llm_provider)

    if wants_payment(text):
        try:
            data = await BillingClient().create_payment_intent(
                user_key=payload.user_key,
                concept="servicio_civi",
                amount=0,
            )
            return AgentTurnResponse(
                text=format_payment_intent_response(data),
                state_version=1,
                mode="payment_intent_created",
                tool_calls=["billing.payment_intent.create"],
            )
        except httpx.HTTPStatusError:
            return AgentTurnResponse(
                text="Uy, no pude preparar el pago. Intentemoslo de nuevo en un momento.",
                state_version=1,
                mode="billing_error",
            )

    if wants_quote(text):
        try:
            service_type = quote_service_for_text(text)
            vehicle_type = extract_vehicle_type(text)
            data = await QuoteClient().create(
                service_type=service_type,
                city=extract_city(text),
                vehicle_type=vehicle_type,
                categoria=vehicle_type,
                cilindraje=extract_displacement(text),
                modelo=extract_model_year(text),
                consulta=text if service_type == "infraccion" else None,
                codigo=extract_infraction_code(text),
            )
            return AgentTurnResponse(
                text=format_quote_response(data),
                state_version=1,
                mode="quote_created",
                tool_calls=["quote.create"],
            )
        except httpx.HTTPStatusError:
            return AgentTurnResponse(
                text="Uy, no pude calcular la referencia. Intentemoslo de nuevo en un momento.",
                state_version=1,
                mode="quote_error",
            )

    pending_response = await _maybe_handle_pending_appointment_selection(payload)
    if pending_response is not None:
        return pending_response

    if wants_city_coverage(text):
        city = extract_city(text)
        if city is None:
            return AgentTurnResponse(
                text="Claro. Dime la ciudad y te reviso si tengo cobertura de tecnomecanica ahi.",
                state_version=1,
                mode="knowledge_city_missing_city",
            )
        try:
            data = await KnowledgeClient().get_city_info(city=city, service_type="tecnomecanica")
            return AgentTurnResponse(
                text=format_city_knowledge_response(data),
                state_version=1,
                mode="knowledge_city",
                tool_calls=["knowledge.city_info"],
            )
        except httpx.HTTPStatusError:
            return AgentTurnResponse(
                text="Uy, no pude revisar la cobertura. Intentemoslo de nuevo en un momento.",
                state_version=1,
                mode="knowledge_error",
            )

    if wants_infraccion_explanation(text) and not wants_knowledge(text):
        code = extract_infraction_code(text)
        if code:
            try:
                data = await QuoteClient().get_infraccion_detail(codigo=code)
                return AgentTurnResponse(
                    text=format_infraccion_detail_response(data),
                    state_version=1,
                    mode="infraccion_detail",
                    tool_calls=["quote.infraccion_detail"],
                )
            except httpx.HTTPStatusError:
                pass

    if wants_knowledge(text):
        domain = knowledge_domain_for_text(text)
        topic = knowledge_topic_for_text(text, domain=domain)
        try:
            data = await KnowledgeClient().get_info(domain=domain, topic=topic)
            return AgentTurnResponse(
                text=format_knowledge_response(data),
                state_version=1,
                mode="knowledge_info",
                tool_calls=["knowledge.get_info"],
            )
        except httpx.HTTPStatusError:
            return AgentTurnResponse(
                text="Uy, no pude consultar la base de conocimiento. Intentemoslo de nuevo en un momento.",
                state_version=1,
                mode="knowledge_error",
            )

    if wants_appointment(text):
        procedure = procedure_for_text(text)
        crc_hint = mentions_crc(text)
        if procedure is None:
            loc = location_for_turn(payload)
            appointment_selection_store.save(
                PendingAppointmentSelection(
                    user_key=payload.user_key,
                    channel=payload.channel,
                    procedure=AWAITING_PROCEDURE,
                    places=[],
                    mentioned_crc=crc_hint,
                    lat=loc[0] if loc else None,
                    lng=loc[1] if loc else None,
                )
            )
            return AgentTurnResponse(
                text="Claro. Dime si la cita es para tecnomecanica, licencia o curso por multa.",
                state_version=1,
                mode="appointment_missing_procedure",
            )

        city = extract_city(text)
        location = location_for_turn(payload)
        starts_at = _parse_appointment_datetime(text)
        if city is None and location is None:
            appointment_selection_store.save(
                PendingAppointmentSelection(
                    user_key=payload.user_key,
                    channel=payload.channel,
                    procedure=procedure,
                    places=[],
                    starts_at=starts_at,
                    mentioned_crc=crc_hint,
                )
            )
            preface = ""
            if crc_hint and procedure == "curso_multa":
                preface = (
                    "Para el *curso por multa* necesitas un *CIA* (Centro Integral de Atencion), "
                    "no un CRC (eso es para examenes de licencia). "
                )
            return AgentTurnResponse(
                text=preface + LOCATION_REQUEST_TEXT,
                state_version=1,
                mode="appointment_missing_location",
            )

        return await _find_places_and_continue_appointment(
            payload,
            procedure=procedure,
            city=city,
            location=location,
            starts_at=starts_at,
            mentioned_crc=crc_hint,
        )

    pending_consult = vehicle_consult_store.get(user_key=payload.user_key, channel=payload.channel)
    # Switching to SOAT/tecno clears a soft multas follow-up pending.
    if (
        pending_consult is not None
        and pending_consult.intent == "multas"
        and wants_vigencia(text)
    ):
        vehicle_consult_store.clear(user_key=payload.user_key, channel=payload.channel)
        pending_consult = None

    # Pure greeting should not reopen "SOAT o tecnomecanica?" pending.
    if (
        is_pure_greeting(text)
        and pending_consult is not None
        and pending_consult.intent is None
    ):
        vehicle_consult_store.clear(user_key=payload.user_key, channel=payload.channel)
        pending_consult = None

    # Greeting / soft close: drop sticky multas city so the next consult asks again.
    if (is_pure_greeting(text) or is_soft_conversation_close(text)) and pending_consult is not None:
        if pending_consult.intent == "multas" and pending_consult.city_resolved:
            vehicle_consult_store.clear(user_key=payload.user_key, channel=payload.channel)
            pending_consult = None
        elif is_soft_conversation_close(text):
            vehicle_consult_store.clear(user_key=payload.user_key, channel=payload.channel)
            pending_consult = None
            return AgentTurnResponse(
                text=CONVERSATION_CLOSED_TEXT,
                state_version=1,
                mode="conversation_closed",
            )

    if pending_consult is not None and pending_consult.intent in {"multas", "runt_profile"}:
        # Multas / RUNT profile use their own slots below; do not treat as SOAT/tecno pending.
        pass
    elif pending_consult is not None:
        placa = placa or pending_consult.placa
        documento = documento or pending_consult.documento

    # Switching vehicle / explicit fresh consult: drop any in-progress slots.
    if wants_other_vehicle(text) or wants_fresh_consult(text):
        last_vehicle_slots_store.clear(user_key=payload.user_key, channel=payload.channel)
        if not fresh_placa:
            placa = None
        if not fresh_documento:
            documento = None
        if pending_consult is not None and pending_consult.intent not in {"multas", "runt_profile"}:
            vehicle_consult_store.clear(user_key=payload.user_key, channel=payload.channel)
            pending_consult = None

    # Reuse last successful SOAT/tecno slots for same-vehicle follow-ups
    # (ej. "ahora su tecno", "ambas", "el del vehiculo anterior").
    # Cleared on reset / "otro vehiculo" so a new consult still asks placa+cedula first.
    vigencia_pending_for_slots = pending_consult is not None and pending_consult.intent not in {
        "multas",
        "runt_profile",
    }
    if (
        (not placa or not documento)
        and not wants_other_vehicle(text)
        and not wants_fresh_consult(text)
        and (
            wants_vigencia(text)
            or wants_same_vehicle_slots(text)
            or vigencia_pending_for_slots
        )
    ):
        last_slots = last_vehicle_slots_store.get(user_key=payload.user_key, channel=payload.channel)
        if last_slots is not None:
            placa = placa or last_slots.placa
            documento = documento or last_slots.documento

    has_both_vehicle_slots = bool(placa and documento)
    captured_fresh_slots = bool(fresh_placa or fresh_documento)
    vigencia_pending = pending_consult is not None and pending_consult.intent not in {
        "multas",
        "runt_profile",
    }
    multas_or_runt_pending = pending_consult is not None and pending_consult.intent in {
        "multas",
        "runt_profile",
    }
    should_handle_vehicle = (
        not multas_or_runt_pending
        and (
            wants_vigencia(text)
            or vigencia_pending
            or (has_both_vehicle_slots and captured_fresh_slots)
        )
    )

    if should_handle_vehicle:
        want_both = wants_both_vigencias(text)
        if wants_vigencia(text) or want_both:
            if want_both:
                intent = "ambos"
            elif wants_soat(text) and not wants_tecno(text):
                intent = "soat"
            elif wants_tecno(text) and not wants_soat(text):
                intent = "tecnomecanica"
            elif wants_soat(text):
                intent = "soat"
            else:
                intent = "tecnomecanica"
        elif pending_consult is not None and pending_consult.intent:
            intent = pending_consult.intent
        elif want_both:
            intent = "ambos"
        else:
            intent = None

        if intent is None:
            vehicle_consult_store.save(
                PendingVehicleConsult(
                    user_key=payload.user_key,
                    channel=payload.channel,
                    intent=None,
                    placa=placa,
                    documento=documento,
                )
            )
            if has_both_vehicle_slots:
                return AgentTurnResponse(
                    text=(
                        f"Veo la placa *{placa}* y el documento *{documento}*. "
                        "¿Consultamos *SOAT* o *tecnomecanica*?"
                    ),
                    state_version=1,
                    mode="vehicle_missing_intent",
                )
            return AgentTurnResponse(
                text=format_vehicle_slots_request(
                    need_placa=not placa,
                    need_documento=not documento,
                ),
                state_version=1,
                mode="vehicle_missing_data",
            )

        if not placa or not documento:
            vehicle_consult_store.save(
                PendingVehicleConsult(
                    user_key=payload.user_key,
                    channel=payload.channel,
                    intent=intent,
                    placa=placa,
                    documento=documento,
                )
            )
            return AgentTurnResponse(
                text=format_vehicle_slots_request(
                    need_placa=not placa,
                    need_documento=not documento,
                ),
                state_version=1,
                mode="vehicle_missing_data",
            )

        last_vehicle_slots_store.save(
            LastVehicleSlots(
                user_key=payload.user_key,
                channel=payload.channel,
                placa=placa,
                documento=documento,
            )
        )
        vehicle_consult_store.clear(user_key=payload.user_key, channel=payload.channel)

        if intent == "ambos":
            return await _run_both_vigencia_consults(
                payload=payload,
                placa=placa,
                documento=documento,
            )

        if payload.channel.lower() == "whatsapp":
            return await _enqueue_consult_job(
                payload=payload,
                intent=intent,
                placa=placa,
                documento=documento,
            )

        try:
            data = await VehicleClient().check_vigencia(placa=placa, documento=documento)
        except httpx.HTTPStatusError:
            return AgentTurnResponse(
                text="Uy, no pude consultar RUNT. Revisa placa y cedula, y lo intentamos de nuevo.",
                state_version=1,
                mode="vehicle_error",
            )

        quote_payload = await _maybe_quote_for_vigencia(intent=intent, data=data)
        tool_calls = ["vehicle.check_vigencia"]
        if quote_payload is not None:
            tool_calls.append("quote.create")

        if intent == "tecnomecanica" and _vigencia_needs_agenda(intent=intent, data=data):
            existing = appointment_selection_store.get(
                user_key=payload.user_key, channel=payload.channel
            )
            loc = location_for_turn(payload)
            appointment_selection_store.save(
                PendingAppointmentSelection(
                    user_key=payload.user_key,
                    channel=payload.channel,
                    procedure="tecnomecanica",
                    places=[],
                    lat=(loc[0] if loc else (existing.lat if existing else None)),
                    lng=(loc[1] if loc else (existing.lng if existing else None)),
                )
            )

        return AgentTurnResponse(
            text=format_vigencia_response(data, intent=intent, quote=quote_payload),
            state_version=1,
            mode=f"vehicle_{intent}",
            tool_calls=tool_calls,
        )

    pending_multas = pending_consult is not None and pending_consult.intent == "multas"
    continue_multas_pending = pending_multas and (
        not bool(pending_consult.city_resolved)
        or bool(fresh_placa or fresh_documento)
        or wants_general_multas_city(text)
        or extract_city(text) is not None
    )
    if wants_multas(text) or continue_multas_pending:
        ciudad = extract_city(text)
        city_resolved = False
        # Re-asking multas without new plate/doc/city always restarts (ask city again).
        # Soft pending only applies when the user sends placa/cedula alone.
        restart_multas_city = (
            wants_multas(text)
            and not fresh_placa
            and not fresh_documento
            and ciudad is None
            and not wants_general_multas_city(text)
        )
        if restart_multas_city:
            vehicle_consult_store.clear(user_key=payload.user_key, channel=payload.channel)
            pending_consult = None
            pending_multas = False
            placa = fresh_placa
            documento = fresh_documento
        elif pending_multas:
            ciudad = ciudad or pending_consult.ciudad
            city_resolved = bool(pending_consult.city_resolved)
            placa = placa or pending_consult.placa
            documento = documento or pending_consult.documento

        if wants_general_multas_city(text):
            ciudad = None
            city_resolved = True
        elif ciudad:
            city_resolved = True

        if not city_resolved:
            vehicle_consult_store.save(
                PendingVehicleConsult(
                    user_key=payload.user_key,
                    channel=payload.channel,
                    intent="multas",
                    placa=placa,
                    documento=documento,
                    ciudad=None,
                    city_resolved=False,
                )
            )
            return AgentTurnResponse(
                text=format_multas_city_request(),
                state_version=1,
                mode="multas_missing_city",
            )

        query = documento or placa
        if not query:
            vehicle_consult_store.save(
                PendingVehicleConsult(
                    user_key=payload.user_key,
                    channel=payload.channel,
                    intent="multas",
                    placa=None,
                    documento=None,
                    ciudad=ciudad,
                    city_resolved=True,
                )
            )
            return AgentTurnResponse(
                text=format_multas_query_request(ciudad=ciudad),
                state_version=1,
                mode="multas_missing_document",
            )

        # Soft pending: same city, next placa/cedula re-enters without LLM.
        vehicle_consult_store.save(
            PendingVehicleConsult(
                user_key=payload.user_key,
                channel=payload.channel,
                intent="multas",
                placa=None,
                documento=None,
                ciudad=ciudad,
                city_resolved=True,
            )
        )

        if payload.channel.lower() == "whatsapp":
            return await _enqueue_consult_job(
                payload=payload,
                intent="multas",
                placa=placa if not documento else None,
                documento=query,
                ciudad=ciudad,
            )

        try:
            data = await VehicleClient().consult_multas(documento=query, ciudad=ciudad)
            return AgentTurnResponse(
                text=format_multas_response(data),
                state_version=1,
                mode="vehicle_multas",
                tool_calls=["vehicle.consult_multas"],
            )
        except httpx.HTTPStatusError:
            return AgentTurnResponse(
                text="Uy, no pude consultar SIMIT. Revisa la placa o cedula y lo intentamos de nuevo.",
                state_version=1,
                mode="multas_error",
            )

    pending_runt = pending_consult is not None and pending_consult.intent == "runt_profile"
    continue_runt_pending = pending_runt and bool(fresh_documento or documento)
    if wants_runt_profile(text) or continue_runt_pending:
        if pending_consult is not None and pending_consult.intent == "multas":
            vehicle_consult_store.clear(user_key=payload.user_key, channel=payload.channel)
        # Explicit "otra licencia / de nuevo" without a new cédula restarts the ask.
        if wants_fresh_consult(text) and not fresh_documento:
            documento = None
            vehicle_consult_store.clear(user_key=payload.user_key, channel=payload.channel)
        if not documento:
            vehicle_consult_store.save(
                PendingVehicleConsult(
                    user_key=payload.user_key,
                    channel=payload.channel,
                    intent="runt_profile",
                    placa=None,
                    documento=None,
                )
            )
            return AgentTurnResponse(
                text=format_runt_profile_document_request(),
                state_version=1,
                mode="runt_profile_missing_document",
            )

        vehicle_consult_store.clear(user_key=payload.user_key, channel=payload.channel)

        if payload.channel.lower() == "whatsapp":
            return await _enqueue_consult_job(
                payload=payload,
                intent="runt_profile",
                documento=documento,
            )

        try:
            data = await VehicleClient().consult_runt_profile(documento=documento)
            return AgentTurnResponse(
                text=format_runt_profile_response(data),
                state_version=1,
                mode="vehicle_runt_profile",
                tool_calls=["vehicle.consult_runt_profile"],
            )
        except httpx.HTTPStatusError:
            return AgentTurnResponse(
                text="Uy, no pude consultar el perfil RUNT. Revisa la cedula y lo intentamos de nuevo.",
                state_version=1,
                mode="runt_profile_error",
            )

    if location_for_turn(payload) is not None:
        return AgentTurnResponse(
            text=(
                "Recibi tu ubicacion. Dime si quieres buscar centro para tecnomecanica, "
                "licencia o curso por multa."
            ),
            state_version=1,
            mode="location_received_missing_procedure",
        )

    return await _answer_with_knowledge_context(payload, llm_provider=llm_provider)


async def _answer_with_knowledge_context(
    payload: AgentTurnRequest,
    *,
    llm_provider: LLMProvider | None = None,
) -> AgentTurnResponse:
    context_blocks: list[str] = []
    tool_calls = ["knowledge.search", "llm.complete"]
    try:
        search = await KnowledgeClient().search(query=payload.text, limit=5)
        hits = search.get("hits") if isinstance(search, dict) else None
        if isinstance(hits, list):
            for hit in hits[:4]:
                if not isinstance(hit, dict):
                    continue
                title = str(hit.get("title") or "").strip()
                body = str(hit.get("body") or "").strip()
                score = hit.get("score")
                if not body:
                    continue
                header = title or "Contexto"
                score_bit = f" (score={score})" if isinstance(score, (int, float)) else ""
                context_blocks.append(f"- {header}{score_bit}: {body}")
    except Exception:
        logger.exception("Failed knowledge corpus search; continuing with LLM only")
        tool_calls = ["llm.complete"]

    if context_blocks:
        user_text = (
            f"Pregunta del usuario: {payload.text}\n\n"
            "Contexto validado de Civi (usa solo esto para hechos legales/montos; "
            "si no alcanza, dilo y no inventes codigos ni tarifas):\n"
            + "\n".join(context_blocks)
        )
    else:
        user_text = (
            f"Pregunta del usuario: {payload.text}\n\n"
            "No hay contexto validado recuperado. No inventes codigos de infraccion ni montos. "
            "Si falta informacion, pide el codigo del comparendo o mas detalle."
        )

    return await _run_llm_fallback(
        payload,
        llm_provider=llm_provider,
        user_text_override=user_text,
        tool_calls=tool_calls,
        mode="knowledge_rag_llm" if context_blocks else "llm_provider",
    )


async def _maybe_handle_partner_decision(payload: AgentTurnRequest) -> AgentTurnResponse | None:
    decision = extract_partner_decision(payload.text)
    if decision is None:
        return None
    action, appointment_id = decision

    try:
        if action == "confirmar":
            data = await AppointmentClient().confirm(appointment_id=appointment_id)
            tool = "appointment.confirm"
            mode = "appointment_partner_confirmed"
        else:
            data = await AppointmentClient().reject(appointment_id=appointment_id)
            tool = "appointment.reject"
            mode = "appointment_partner_rejected"
        success = bool(data.get("success"))
        if not success:
            mode = "appointment_partner_decision_failed"
        return AgentTurnResponse(
            text=format_partner_decision_response(
                action=action,
                appointment_id=appointment_id,
                success=success,
                error=str(data.get("error") or "") or None,
            ),
            state_version=1,
            mode=mode,
            tool_calls=[tool],
        )
    except httpx.HTTPStatusError:
        return AgentTurnResponse(
            text=format_partner_decision_response(
                action=action,
                appointment_id=appointment_id,
                success=False,
            ),
            state_version=1,
            mode="appointment_partner_decision_error",
        )


async def _maybe_handle_pending_appointment_selection(payload: AgentTurnRequest) -> AgentTurnResponse | None:
    pending = appointment_selection_store.get(user_key=payload.user_key, channel=payload.channel)
    was_just_loaded = False
    if pending is None:
        row = shared_pending_store.pop_pending(user_key=payload.user_key)
        if row:
            pending = PendingAppointmentSelection(
                user_key=payload.user_key,
                channel=payload.channel,
                procedure=row["procedure"],
                places=[],
                lat=row.get("lat"),
                lng=row.get("lng"),
            )
            appointment_selection_store.save(pending)
            was_just_loaded = True
        else:
            return None

    # Refresh pin from this turn's metadata if present.
    meta_loc = _location_from_metadata(payload)
    if meta_loc is not None:
        pending.lat, pending.lng = meta_loc
        appointment_selection_store.save(pending)

    # Mid-flow escapes: greeting / soft close / abandon / /restart must free the selection trap.
    if is_pure_greeting(payload.text):
        appointment_selection_store.clear(user_key=payload.user_key, channel=payload.channel)
        shared_pending_store.clear(user_key=payload.user_key)
        return None
    if is_soft_conversation_close(payload.text):
        appointment_selection_store.clear(user_key=payload.user_key, channel=payload.channel)
        shared_pending_store.clear(user_key=payload.user_key)
        return AgentTurnResponse(
            text=CONVERSATION_CLOSED_TEXT,
            state_version=1,
            mode="conversation_closed",
        )
    if wants_abandon_appointment_flow(payload.text):
        appointment_selection_store.clear(user_key=payload.user_key, channel=payload.channel)
        shared_pending_store.clear(user_key=payload.user_key)
        return AgentTurnResponse(
            text="Listo, deje la agenda por ahora. Si luego quieres cita, me dices.",
            state_version=1,
            mode="appointment_flow_abandoned",
        )

    if mentions_crc(payload.text):
        pending.mentioned_crc = True

    # Resolve procedure when user was asked for tecnomecanica / licencia / curso.
    if pending.procedure in {"", AWAITING_PROCEDURE}:
        resolved = procedure_for_text(payload.text)
        if resolved is None:
            appointment_selection_store.save(pending)
            # Pin-first or explicit "agendar" without procedure → ask.
            # Otherwise keep lat/lng silently and let other intents run.
            pin_this_turn = _location_from_metadata(payload) is not None
            if wants_appointment(payload.text) or pin_this_turn:
                return AgentTurnResponse(
                    text="Claro. Dime si la cita es para tecnomecanica, licencia o curso por multa.",
                    state_version=1,
                    mode="appointment_missing_procedure",
                )
            return None
        pending.procedure = resolved
        appointment_selection_store.save(pending)

    starts_at = _parse_appointment_datetime(payload.text)
    if starts_at:
        pending.starts_at = starts_at

    if not pending.places:
        city = extract_city(payload.text)
        location = location_for_turn(payload)
        if city is None and location is None:
            appointment_selection_store.save(pending)
            preface = ""
            if pending.mentioned_crc and pending.procedure == "curso_multa":
                preface = (
                    "Para el *curso por multa* necesitas un *CIA* (Centro Integral de Atencion), "
                    "no un CRC (eso es para examenes de licencia). "
                )
            if (
                starts_at
                or was_just_loaded
                or wants_appointment(payload.text)
                or procedure_for_text(payload.text) is not None
            ):
                return AgentTurnResponse(
                    text=preface + LOCATION_REQUEST_PENDING_TEXT,
                    state_version=1,
                    mode="appointment_missing_location",
                )
            return None

        return await _find_places_and_continue_appointment(
            payload,
            procedure=pending.procedure,
            city=city,
            location=location,
            starts_at=pending.starts_at,
            mentioned_crc=pending.mentioned_crc,
        )

    if wants_place_comparison(payload.text) and pending.places:
        return AgentTurnResponse(
            text=format_place_comparison_response(pending.places),
            state_version=1,
            mode="appointment_place_comparison",
            tool_calls=[],
        )

    # extract_place_selection strips time fragments so "a las 8 pm" is not center #8,
    # while "el 2 manana a las 10" can still switch centers.
    selection_idx = extract_place_selection(payload.text, places=pending.places)

    if selection_idx is None and wants_nearest_place(payload.text) and pending.places:
        selection_idx = extract_place_selection("el mas cercano", places=pending.places)

    if selection_idx is None and _looks_like_place_confirmation(payload.text):
        if pending.selected_index is not None:
            selection_idx = pending.selected_index
        elif len(pending.places) == 1:
            selection_idx = 1

    if wants_alternative_places(payload.text) and selection_idx is None:
        return AgentTurnResponse(
            text=format_place_options_response(pending.places, starts_at=pending.starts_at),
            state_version=1,
            mode="appointment_place_options",
            tool_calls=[],
        )

    previous_selected = pending.selected_index
    if selection_idx is not None:
        if not (1 <= selection_idx <= len(pending.places)):
            return AgentTurnResponse(
                text=f"Claro. Elige una opcion entre 1 y {len(pending.places)}, o dime el nombre del centro.",
                state_version=1,
                mode="appointment_place_selection_invalid",
            )
        pending.selected_index = selection_idx
        appointment_selection_store.save(pending)

    if pending.selected_index is None and len(pending.places) == 1:
        pending.selected_index = 1
        appointment_selection_store.save(pending)

    if pending.selected_index is not None and not pending.starts_at:
        place = pending.places[pending.selected_index - 1]
        if _has_datetime_hint(payload.text):
            time_mention = _extract_time_mention(payload.text)
            if time_mention:
                msg = f"Entendido, {time_mention}. ¿Para qué día?"
            else:
                msg = "Entendido, vi la hora que mencionas. ¿Para qué día la necesitas?"
            return AgentTurnResponse(
                text=msg,
                state_version=1,
                mode="appointment_missing_date",
            )
        return AgentTurnResponse(
            text=format_pending_place_date_request(place),
            state_version=1,
            mode="appointment_missing_date",
        )

    if pending.selected_index is None and pending.starts_at:
        appointment_selection_store.save(pending)
        return AgentTurnResponse(
            text=format_place_options_response(pending.places, starts_at=pending.starts_at),
            state_version=1,
            mode="appointment_place_selection_required",
        )

    if pending.selected_index is None or not pending.starts_at:
        # Keep the pending alive; ask again instead of falling through to LLM.
        if pending.places:
            return AgentTurnResponse(
                text=(
                    "Dime el *numero* o el *nombre* del centro de la lista. "
                    "Si quieres, tambien puedo decirte cual queda mas cerca."
                ),
                state_version=1,
                mode="appointment_place_selection_required",
            )
        return None

    place = pending.places[pending.selected_index - 1]
    already_booked_same = (
        pending.created_appointment_id is not None
        and (selection_idx is None or selection_idx == previous_selected)
    )
    if already_booked_same:
        # Post-create pending is only for replace-by-different-center.
        # Any other message closes it so normal intents can run.
        appointment_selection_store.clear(user_key=payload.user_key, channel=payload.channel)
        shared_pending_store.clear(user_key=payload.user_key)
        return None

    try:
        cancel_note = ""
        tool_calls: list[str] = []
        if pending.created_appointment_id is not None:
            try:
                await AppointmentClient().cancel(
                    user_key=payload.user_key,
                    appointment_id=pending.created_appointment_id,
                )
                tool_calls.append("appointment.cancel")
                cancel_note = (
                    f"Cancele la solicitud anterior *#{pending.created_appointment_id}* y "
                )
            except httpx.HTTPStatusError:
                cancel_note = (
                    f"Intente reemplazar la solicitud *#{pending.created_appointment_id}*; "
                    "si el centro ya la habia tomado, avisa. "
                )

        appointment_data = await AppointmentClient().create(
            user_key=payload.user_key,
            procedure=pending.procedure,
            starts_at=pending.starts_at,
            place=place,
            notification_to=notification_to_for_turn(payload),
        )
        created = appointment_data.get("appointment") or {}
        created_id = created.get("id")
        pending.created_appointment_id = int(created_id) if created_id is not None else None
        appointment_selection_store.save(pending)
        shared_pending_store.clear(user_key=payload.user_key)
        tool_calls.extend(["appointment.select_place", "appointment.create"])
        if (appointment_data.get("notification") or {}).get("status") == "sent":
            tool_calls.append("notification.partner_notify")
        body = format_appointment_response(created)
        if cancel_note:
            body = cancel_note + body
        return AgentTurnResponse(
            text=body,
            state_version=1,
            mode="appointment_replaced" if cancel_note else "appointment_created",
            tool_calls=tool_calls,
        )
    except httpx.HTTPStatusError:
        return AgentTurnResponse(
            text="Uy, no pude crear la cita. Intentemoslo de nuevo en un momento.",
            state_version=1,
            mode="appointment_error",
        )


async def _find_places_and_continue_appointment(
    payload: AgentTurnRequest,
    *,
    procedure: str,
    city: str | None,
    location: tuple[float, float] | None,
    starts_at: str | None,
    mentioned_crc: bool = False,
) -> AgentTurnResponse:
    lat = location[0] if location is not None else None
    lng = location[1] if location is not None else None
    try:
        places_data = await PlacesClient().find_nearest(procedure=procedure, city=city, lat=lat, lng=lng)
    except httpx.HTTPStatusError:
        return AgentTurnResponse(
            text="Uy, no pude buscar centros cercanos. Intentemoslo de nuevo en un momento.",
            state_version=1,
            mode="places_error",
        )

    places = places_data.get("places") or []
    crc_note = ""
    if mentioned_crc and procedure == "curso_multa":
        crc_note = (
            "Para el *curso por multa* necesitas un *CIA* (Centro Integral de Atencion), "
            "no un CRC (eso es para examenes de licencia). "
        )

    if not places:
        reason = places_data.get("no_results_reason")
        empty_text = "Aun no tengo centros disponibles para ese tramite en esa ciudad."
        if reason == "no_sites_within_radius":
            empty_text = "No encontre centros dentro del radio de busqueda para esa ubicacion."
        elif reason == "no_coverage_in_municipality":
            empty_text = "No tengo cobertura de centros para ese tramite en ese municipio."
        elif reason == "city_or_coordinates_required":
            empty_text = (
                "Para buscarte el centro necesito la ciudad o tu ubicacion por WhatsApp. "
                "No puedo asumir un municipio."
            )
        elif reason == "coordinates_outside_colombia":
            empty_text = "La ubicacion que enviaste esta fuera de Colombia. Comparte una ubicacion valida."
        return AgentTurnResponse(
            text=crc_note + empty_text,
            state_version=1,
            mode="places_empty",
            tool_calls=["places.find_nearest"],
        )

    bookable_places = [place for place in places if place.get("is_bookable") is True]
    informative_places = [place for place in places if place.get("is_bookable") is not True]

    if not bookable_places:
        return AgentTurnResponse(
            text=crc_note + format_informative_places_response(informative_places or places),
            state_version=1,
            mode="places_informative_only",
            tool_calls=["places.find_nearest"],
        )

    if len(bookable_places) > 1:
        appointment_selection_store.save(
            PendingAppointmentSelection(
                user_key=payload.user_key,
                channel=payload.channel,
                procedure=procedure,
                places=[dict(place) for place in bookable_places],
                starts_at=starts_at,
                mentioned_crc=mentioned_crc,
                lat=lat,
                lng=lng,
            )
        )
        return AgentTurnResponse(
            text=crc_note + format_place_options_response(bookable_places, starts_at=starts_at),
            state_version=1,
            mode="appointment_place_selection_required",
            tool_calls=["places.find_nearest"],
        )

    if not starts_at:
        appointment_selection_store.save(
            PendingAppointmentSelection(
                user_key=payload.user_key,
                channel=payload.channel,
                procedure=procedure,
                places=[dict(bookable_places[0])],
                mentioned_crc=mentioned_crc,
                lat=lat,
                lng=lng,
            )
        )
        return AgentTurnResponse(
            text=crc_note + format_place_response(bookable_places[0]),
            state_version=1,
            mode="places_suggested",
            tool_calls=["places.find_nearest"],
        )

    try:
        appointment_data = await AppointmentClient().create(
            user_key=payload.user_key,
            procedure=procedure,
            starts_at=starts_at,
            place=bookable_places[0],
            notification_to=notification_to_for_turn(payload),
        )
        appointment_selection_store.clear(user_key=payload.user_key, channel=payload.channel)
        shared_pending_store.clear(user_key=payload.user_key)
        tool_calls = ["places.find_nearest", "appointment.create"]
        if (appointment_data.get("notification") or {}).get("status") == "sent":
            tool_calls.append("notification.partner_notify")
        return AgentTurnResponse(
            text=format_appointment_response(appointment_data["appointment"]),
            state_version=1,
            mode="appointment_created",
            tool_calls=tool_calls,
        )
    except httpx.HTTPStatusError:
        return AgentTurnResponse(
            text="Uy, no pude crear la cita. Intentemoslo de nuevo en un momento.",
            state_version=1,
            mode="appointment_error",
        )


async def _run_llm_fallback(
    payload: AgentTurnRequest,
    *,
    llm_provider: LLMProvider | None = None,
    user_text_override: str | None = None,
    tool_calls: list[str] | None = None,
    mode: str | None = None,
) -> AgentTurnResponse:
    provider = llm_provider or llm_provider_from_env()
    history = history_from_recent_turns((payload.metadata or {}).get("recent_turns"))
    try:
        result = await provider.complete(
            system_prompt=build_system_prompt(),
            user_text=user_text_override or payload.text,
            user_key=payload.user_key,
            channel=payload.channel,
            history=history or None,
        )
    except httpx.HTTPStatusError:
        return AgentTurnResponse(
            text="Uy, se me cruzaron los cables un segundo. Intentemoslo de nuevo en un momento.",
            state_version=1,
            mode="llm_error",
        )

    generated = result.get("text")
    if isinstance(generated, str) and generated.strip():
        return AgentTurnResponse(
            text=generated.strip(),
            state_version=1,
            mode=mode or str(result.get("provider_mode", "llm_provider")),
            tool_calls=tool_calls or ["llm.complete"],
        )

    return AgentTurnResponse(
        text="¡Hola! Soy Civi, tu asistente integral de tránsito en Colombia. ¿En qué puedo ayudarte? 😊",
        state_version=1,
        mode="agent_menu",
    )


LOCATION_REQUEST_TEXT = (
    "Dale, con gusto. Para buscarte el centro mas cercano necesito tu ubicacion: "
    "mandamela por WhatsApp o escribieme la ciudad donde quieres agendar."
)

LOCATION_REQUEST_PENDING_TEXT = (
    "Perfecto, ya tengo el tramite. Ahora comparteme tu ubicacion por WhatsApp "
    "o dime la ciudad y te busco centros cercanos."
)

PLACE_CONFIRMATION_PATTERNS: tuple[str, ...] = (
    "si",
    "sisas",
    "sip",
    "dale",
    "va",
    "vale",
    "ok",
    "okay",
    "listo",
    "perfecto",
    "me sirve",
    "esa esta bien",
    "esa me sirve",
    "confirmo",
    "hagale",
    "de una",
    "esta bien",
)

NEGATED_PLACE_CONFIRMATION = re.compile(r"\b(no|nunca|jamas|tampoco)\s+(me\s+sirve|va|vale|ok|listo|dale)\b")


def _parse_appointment_datetime(text: str) -> str | None:
    natural = parse_natural_datetime(text or "")
    if natural:
        return natural
    return extract_start_iso(text or "")


def _normalize_for_confirmation(text: str) -> str:
    decomposed = unicodedata.normalize("NFKD", text or "")
    ascii_text = "".join(char for char in decomposed if not unicodedata.combining(char))
    collapsed = " ".join(ascii_text.lower().strip().split())
    return re.sub(r"[!?\.,;:]", "", collapsed).strip()


def _looks_like_place_confirmation(text: str) -> bool:
    normalized = _normalize_for_confirmation(text)
    if not normalized:
        return False
    if NEGATED_PLACE_CONFIRMATION.search(normalized):
        return False
    if normalized in {"si", "sip", "s", "dale", "va", "vale", "ok", "okay", "listo"}:
        return True
    return any(pattern in normalized for pattern in PLACE_CONFIRMATION_PATTERNS)


_TIME_MENTION_RE = re.compile(
    r"(?:(?:a|para)\s+las?\s+)?\d{1,2}(?::\d{2})?(?:\s*(?:am|pm))?(?:\s+de\s+la\s+(?:manana|tarde|noche))?",
    re.IGNORECASE,
)


def _extract_time_mention(text: str) -> str | None:
    """Extract a human-readable time mention from text for acknowledgment."""
    normalized = _normalize_for_confirmation(text)
    match = _TIME_MENTION_RE.search(normalized)
    if not match:
        return None
    raw = match.group(0).strip()
    if not raw or raw.isdigit():
        return None
    return raw


def _vigencia_needs_agenda(*, intent: str, data: dict) -> bool:
    if intent == "tecnomecanica":
        return tecno_needs_quote(data)
    return False


async def _maybe_quote_for_vigencia(*, intent: str, data: dict) -> dict | None:
    if intent == "tecnomecanica":
        if not tecno_needs_quote(data):
            return None
        vehiculo = data.get("vehiculo") or {}
        categoria = map_clase_to_quote_category(vehiculo.get("claseVehiculo"))
        if categoria is None:
            return None
        try:
            return await QuoteClient().create(service_type="tecnomecanica", categoria=categoria)
        except (httpx.HTTPError, RuntimeError) as exc:
            logger.warning("quote tecnomecanica failed best-effort: %s", exc)
            return None

    if intent == "soat":
        if not soat_needs_quote(data):
            return None
        vehiculo = data.get("vehiculo") or {}
        categoria = map_clase_to_quote_category(vehiculo.get("claseVehiculo"))
        if categoria not in {"moto", "carro", "campero", "camioneta", "taxi"}:
            return None
        cilindraje = _int_or_none(vehiculo.get("cilindraje"))
        modelo = _int_or_none(vehiculo.get("modelo"))
        if cilindraje is None or modelo is None:
            return None
        try:
            return await QuoteClient().create(
                service_type="soat",
                vehicle_type=categoria,
                cilindraje=cilindraje,
                modelo=modelo,
            )
        except (httpx.HTTPError, RuntimeError) as exc:
            logger.warning("quote soat failed best-effort: %s", exc)
            return None

    return None


def _int_or_none(value: object) -> int | None:
    if isinstance(value, bool):
        return None
    if isinstance(value, int):
        return value
    if isinstance(value, float):
        return int(value)
    if isinstance(value, str):
        stripped = value.strip()
        if not stripped:
            return None
        try:
            return int(float(stripped))
        except ValueError:
            return None
    return None


def _int_from_env(name: str, default: int) -> int:
    raw = os.getenv(name, "").strip()
    try:
        value = int(raw)
    except ValueError:
        return default
    return value if value >= 0 else default


def notification_to_for_turn(payload: AgentTurnRequest) -> str | None:
    if payload.channel.lower() != "whatsapp":
        return None
    normalized = re.sub(r"\D", "", payload.user_key or "")
    if PHONE_USER_KEY_RE.match(normalized):
        return normalized
    return None


def _location_from_metadata(payload: AgentTurnRequest) -> tuple[float, float] | None:
    metadata = payload.metadata or {}
    for lat_key, lng_key in (
        ("location_lat", "location_lng"),
        ("geo_lat", "geo_lng"),
        ("lat", "lng"),
    ):
        if lat_key not in metadata or lng_key not in metadata:
            continue
        try:
            lat = float(metadata[lat_key])
            lng = float(metadata[lng_key])
        except (TypeError, ValueError):
            continue
        if is_colombia_latlng(lat, lng):
            return lat, lng
    return None


def _capture_turn_location(payload: AgentTurnRequest) -> None:
    """Persist pin from this turn into pending so later text turns keep GPS."""
    loc = _location_from_metadata(payload)
    if loc is None:
        return
    pending = appointment_selection_store.get(user_key=payload.user_key, channel=payload.channel)
    if pending is None:
        pending = PendingAppointmentSelection(
            user_key=payload.user_key,
            channel=payload.channel,
            procedure=AWAITING_PROCEDURE,
            places=[],
            lat=loc[0],
            lng=loc[1],
        )
    else:
        pending.lat, pending.lng = loc
    appointment_selection_store.save(pending)
    if pending.procedure and pending.procedure != AWAITING_PROCEDURE:
        shared_pending_store.save(
            user_key=payload.user_key,
            channel=payload.channel,
            procedure=pending.procedure,
            lat=pending.lat,
            lng=pending.lng,
        )


def location_for_turn(payload: AgentTurnRequest) -> tuple[float, float] | None:
    meta = _location_from_metadata(payload)
    if meta is not None:
        return meta
    pending = appointment_selection_store.get(user_key=payload.user_key, channel=payload.channel)
    if pending is not None and pending.lat is not None and pending.lng is not None:
        if is_colombia_latlng(pending.lat, pending.lng):
            return pending.lat, pending.lng
    return None


async def _run_both_vigencia_consults(
    *,
    payload: AgentTurnRequest,
    placa: str,
    documento: str,
) -> AgentTurnResponse:
    """Consult SOAT and tecnomecanica for the same plate/document without a new job schema."""
    if payload.channel.lower() == "whatsapp":
        soat_response = await _enqueue_consult_job(
            payload=payload,
            intent="soat",
            placa=placa,
            documento=documento,
        )
        tecno_response = await _enqueue_consult_job(
            payload=payload,
            intent="tecnomecanica",
            placa=placa,
            documento=documento,
        )
        # Prefer a single clear ack; avoid stacking two near-identical queue messages.
        if soat_response.mode.endswith("_already_processing") or tecno_response.mode.endswith(
            "_already_processing"
        ):
            return AgentTurnResponse(
                text="Tus consultas de SOAT y tecnomecanica ya van en camino. En un momento te mando los resultados por aqui.",
                state_version=1,
                mode="vehicle_ambos_already_processing",
                tool_calls=["vehicle.check_vigencia"],
            )
        return AgentTurnResponse(
            text=(
                "Listo, ya empiezo a consultar tu *SOAT* y tu *tecnomecanica* en el RUNT. "
                "En un momento te mando ambos resultados por aqui."
            ),
            state_version=1,
            mode="vehicle_ambos_queued",
            tool_calls=["vehicle.check_vigencia"],
        )

    try:
        data = await VehicleClient().check_vigencia(placa=placa, documento=documento)
    except httpx.HTTPStatusError:
        return AgentTurnResponse(
            text="Uy, no pude consultar RUNT. Revisa placa y cedula, y lo intentamos de nuevo.",
            state_version=1,
            mode="vehicle_error",
        )

    soat_quote = await _maybe_quote_for_vigencia(intent="soat", data=data)
    tecno_quote = await _maybe_quote_for_vigencia(intent="tecnomecanica", data=data)
    soat_text = format_vigencia_response(data, intent="soat", quote=soat_quote)
    tecno_text = format_vigencia_response(data, intent="tecnomecanica", quote=tecno_quote)
    tool_calls = ["vehicle.check_vigencia"]
    if soat_quote is not None or tecno_quote is not None:
        tool_calls.append("quote.create")
    return AgentTurnResponse(
        text=f"{soat_text}\n\n{tecno_text}",
        state_version=1,
        mode="vehicle_ambos",
        tool_calls=tool_calls,
    )


async def _enqueue_consult_job(
    *,
    payload: AgentTurnRequest,
    intent: str,
    placa: str | None = None,
    documento: str | None = None,
    ciudad: str | None = None,
    repository: "ConsultJobRepository | None" = None,
) -> AgentTurnResponse:
    repo = repository or get_consult_job_repository()

    parallelism = _int_from_env("BOT_CONSULT_MAX_CONCURRENT", 3)
    dedup_window = _int_from_env("BOT_CONSULT_DEDUP_WINDOW_SECONDS", 120)
    if dedup_window > 0:
        existing = repo.find_active_for_user(
            user_key=payload.user_key,
            intent=intent,
            max_age_seconds=dedup_window,
        )
        if existing is not None:
            existing_job, existing_pos = existing
            if existing_job.status == ConsultJobStatus.PROCESSING:
                return AgentTurnResponse(
                    text="Tu consulta ya va en camino. En un momento te mando el resultado por aqui.",
                    state_version=1,
                    mode=f"vehicle_{intent}_already_processing",
                )
            # Still pending — reuse existing position
            intent_labels: dict[str, str] = {
                "soat": "SOAT",
                "tecnomecanica": "tecnomecanica",
                "multas": "multas",
                "runt_profile": "perfil RUNT",
            }
            label = intent_labels.get(intent, intent)
            wait_estimate = estimated_wait_seconds(existing_pos, parallelism=parallelism)
            return AgentTurnResponse(
                text=(
                    f"Ya tienes una consulta de {label} en la cola "
                    f"(posicion *{existing_pos}*, espera estimada: {wait_estimate}). "
                    f"Te mando el resultado por aqui apenas este listo."
                ),
                state_version=1,
                mode=f"vehicle_{intent}_already_queued",
            )

    job = ConsultJob(
        job_id=generate_job_id(),
        user_key=payload.user_key,
        channel=payload.channel,
        intent=intent,
        placa=placa,
        documento=documento,
        ciudad=ciudad,
    )
    try:
        _, position = repo.enqueue(job)
    except RuntimeError:
        return AgentTurnResponse(
            text="Hay muchas consultas en curso ahora. Intentemoslo de nuevo en un momentico.",
            state_version=1,
            mode="vehicle_queue_full",
        )

    intent_labels: dict[str, str] = {
        "soat": "SOAT",
        "tecnomecanica": "tecnomecanica",
        "multas": "multas",
        "runt_profile": "perfil RUNT",
    }
    label = intent_labels.get(intent, intent)
    wait_estimate = estimated_wait_seconds(position, parallelism=parallelism)

    if position == 1:
        if intent == "multas":
            city_bit = f" en *{ciudad}*" if ciudad else " a nivel nacional"
            msg = (
                f"Listo, ya empiezo a consultar tus multas{city_bit} en SIMIT "
                f"(y el portal local si aplica). En un momento te mando el resultado por aqui."
            )
        else:
            msg = (
                f"Listo, ya empiezo a consultar tu {label} en el RUNT. "
                f"En un momento te mando el resultado por aqui."
            )
    else:
        msg = (
            f"Listo, tu consulta de {label} quedo en la posicion *{position}* de la cola "
            f"(espera estimada: {wait_estimate}). "
            f"Te mando el resultado por aqui apenas este listo."
        )

    tool_calls: list[str]
    if intent == "soat" or intent == "tecnomecanica":
        tool_calls = ["vehicle.check_vigencia"]
    elif intent == "multas":
        tool_calls = ["vehicle.consult_multas"]
    elif intent == "runt_profile":
        tool_calls = ["vehicle.consult_runt_profile"]
    else:
        tool_calls = []

    return AgentTurnResponse(
        text=msg,
        state_version=1,
        mode=f"vehicle_{intent}_queued",
        tool_calls=tool_calls,
    )
