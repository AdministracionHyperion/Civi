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
from bot_orchestrator.adapters.outbound.llm_provider import LLMProvider, llm_provider_from_env
from bot_orchestrator.adapters.outbound.notification_client import NotificationClient
from bot_orchestrator.adapters.outbound.places_client import PlacesClient
from bot_orchestrator.adapters.outbound.quote_client import QuoteClient
from bot_orchestrator.adapters.outbound.vehicle_client import VehicleClient
from bot_orchestrator.prompts.loader import build_system_prompt
from bot_orchestrator.shared.appointment_selection import (
    AWAITING_PROCEDURE,
    PendingAppointmentSelection,
    PendingVehicleConsult,
    appointment_selection_store,
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
    wants_appointment,
    wants_cancel_appointment,
    wants_city_coverage,
    wants_alternative_places,
    wants_general_multas_city,
    wants_handoff,
    wants_knowledge,
    wants_multas,
    wants_payment,
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
)
from .formatters import (
    format_appointment_response,
    format_appointments_list,
    format_cancel_appointment_response,
    format_city_knowledge_response,
    format_knowledge_response,
    format_multas_response,
    format_no_affiliate_coverage,
    format_partner_decision_response,
    format_pending_place_date_request,
    format_place_response,
    format_place_options_response,
    format_payment_intent_response,
    format_quote_response,
    format_reminder_response,
    format_runt_profile_response,
    format_handoff_response,
    format_infraccion_detail_response,
    format_vigencia_response,
    soat_needs_quote,
    tecno_needs_quote,
)
from .schemas import AgentTurnRequest, AgentTurnResponse

logger = logging.getLogger(__name__)

PHONE_USER_KEY_RE = re.compile(r"^\+?[0-9]{10,15}$")


async def run_agent_turn(
    payload: AgentTurnRequest,
    *,
    llm_provider: LLMProvider | None = None,
) -> AgentTurnResponse:
    text = payload.text
    fresh_placa = extract_plate(text)
    fresh_documento = extract_document(text)
    placa = fresh_placa
    documento = fresh_documento

    lowered = text.lower()
    partner_response = await _maybe_handle_partner_decision(payload)
    if partner_response is not None:
        return partner_response

    if wants_cancel_appointment(text):
        appointment_id = extract_appointment_id(text)
        if appointment_id is None:
            return AgentTurnResponse(
                text="Dime el ID de la cita que quieres cancelar. Si no lo tienes, pregunta por tus citas primero.",
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
                text="Tuve un problema cancelando la cita. Intentalo de nuevo en un momento.",
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
                text="Tuve un problema revisando tus citas. Intentalo de nuevo en un momento.",
                state_version=1,
                mode="appointments_error",
            )

    if wants_reminder(text):
        remind_at = _parse_appointment_datetime(text)
        notification_to = notification_to_for_turn(payload)
        if not remind_at:
            return AgentTurnResponse(
                text="Dime la fecha y hora del recordatorio, por ejemplo manana a las 10 o 2026-07-10 09:00.",
                state_version=1,
                mode="reminder_missing_date",
            )
        if not notification_to:
            return AgentTurnResponse(
                text="Puedo programarlo cuando el canal tenga un numero WhatsApp valido.",
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
                text="Tuve un problema programando el recordatorio. Intentalo de nuevo en un momento.",
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
                text="Tuve un problema creando el caso para un asesor. Intentalo de nuevo en un momento.",
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
                text="Tuve un problema preparando el pago. Intentalo de nuevo en un momento.",
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
                text="Tuve un problema calculando la referencia. Intentalo de nuevo en un momento.",
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
                text="Dime la ciudad para validar si tengo cobertura de tecnomecanica cargada ahi.",
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
                text="Tuve un problema revisando cobertura. Intentalo de nuevo en un momento.",
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
                text="Tuve un problema consultando la base de conocimiento. Intentalo de nuevo en un momento.",
                state_version=1,
                mode="knowledge_error",
            )

    if wants_appointment(text):
        procedure = procedure_for_text(text)
        crc_hint = mentions_crc(text)
        if procedure is None:
            appointment_selection_store.save(
                PendingAppointmentSelection(
                    user_key=payload.user_key,
                    channel=payload.channel,
                    procedure=AWAITING_PROCEDURE,
                    places=[],
                    mentioned_crc=crc_hint,
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
    if pending_consult is not None and pending_consult.intent in {"multas", "runt_profile"}:
        # Multas / RUNT profile use their own slots below; do not treat as SOAT/tecno pending.
        pass
    elif pending_consult is not None:
        placa = placa or pending_consult.placa
        documento = documento or pending_consult.documento

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
        if wants_vigencia(text):
            intent = "soat" if wants_soat(text) and not wants_tecno(text) else "tecnomecanica"
        elif pending_consult is not None and pending_consult.intent:
            intent = pending_consult.intent
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
            missing_bits: list[str] = []
            if not placa:
                missing_bits.append("la *placa*")
            if not documento:
                missing_bits.append("la *cedula del titular*")
            missing = " y ".join(missing_bits) if missing_bits else "la *placa* y la *cedula*"
            return AgentTurnResponse(
                text=f"Para consultar SOAT o tecnomecanica, pasame {missing}.",
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
            if not placa and not documento:
                missing_prompt = (
                    "Va el SOAT. Pasame la *placa* y la *cedula del titular* y consulto en RUNT."
                    if intent == "soat"
                    else "Va la tecno. Pasame la *placa* y la *cedula del titular* y consulto en RUNT."
                )
            elif not placa:
                missing_prompt = (
                    "Va el SOAT. Pasame la *placa* y consulto en RUNT."
                    if intent == "soat"
                    else "Va la tecno. Pasame la *placa* y consulto en RUNT."
                )
            else:
                missing_prompt = (
                    "Va el SOAT. Pasame la *cedula del titular* y consulto en RUNT."
                    if intent == "soat"
                    else "Va la tecno. Pasame la *cedula del titular* y consulto en RUNT."
                )
            return AgentTurnResponse(
                text=missing_prompt,
                state_version=1,
                mode="vehicle_missing_data",
            )

        vehicle_consult_store.clear(user_key=payload.user_key, channel=payload.channel)

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
                text="Tuve un problema consultando RUNT. Verifica placa y cedula, y lo intento de nuevo.",
                state_version=1,
                mode="vehicle_error",
            )

        quote_payload = await _maybe_quote_for_vigencia(intent=intent, data=data)
        tool_calls = ["vehicle.check_vigencia"]
        if quote_payload is not None:
            tool_calls.append("quote.create")

        if intent == "tecnomecanica" and _vigencia_needs_agenda(intent=intent, data=data):
            appointment_selection_store.save(
                PendingAppointmentSelection(
                    user_key=payload.user_key,
                    channel=payload.channel,
                    procedure="tecnomecanica",
                    places=[],
                )
            )

        return AgentTurnResponse(
            text=format_vigencia_response(data, intent=intent, quote=quote_payload),
            state_version=1,
            mode=f"vehicle_{intent}",
            tool_calls=tool_calls,
        )

    if wants_multas(text) or (
        pending_consult is not None and pending_consult.intent == "multas"
    ):
        ciudad = extract_city(text)
        if pending_consult is not None and pending_consult.intent == "multas":
            ciudad = ciudad or pending_consult.ciudad
            documento = documento or pending_consult.documento

        if wants_general_multas_city(text):
            ciudad = None

        if not documento:
            vehicle_consult_store.save(
                PendingVehicleConsult(
                    user_key=payload.user_key,
                    channel=payload.channel,
                    intent="multas",
                    documento=None,
                    ciudad=ciudad,
                )
            )
            if ciudad:
                ask = f"Va. Para consultar multas en *{ciudad}*, pasame la *cedula*."
            else:
                ask = "Va. Consulto en SIMIT nacional. Pasame la *cedula*."
            return AgentTurnResponse(
                text=ask,
                state_version=1,
                mode="multas_missing_document",
            )

        vehicle_consult_store.clear(user_key=payload.user_key, channel=payload.channel)

        if payload.channel.lower() == "whatsapp":
            return await _enqueue_consult_job(
                payload=payload,
                intent="multas",
                documento=documento,
                ciudad=ciudad,
            )

        try:
            data = await VehicleClient().consult_multas(documento=documento, ciudad=ciudad)
            return AgentTurnResponse(
                text=format_multas_response(data),
                state_version=1,
                mode="vehicle_multas",
                tool_calls=["vehicle.consult_multas"],
            )
        except httpx.HTTPStatusError:
            return AgentTurnResponse(
                text="Tuve un problema consultando SIMIT. Verifica la cedula y lo intento de nuevo.",
                state_version=1,
                mode="multas_error",
            )

    if wants_runt_profile(text):
        if not documento:
            return AgentTurnResponse(
                text="Pasame la *cedula* para consultar tu perfil RUNT.",
                state_version=1,
                mode="runt_profile_missing_document",
            )

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
                text="Tuve un problema consultando el perfil RUNT. Verifica la cedula y lo intento de nuevo.",
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
        procedure = shared_pending_store.pop_pending_procedure(user_key=payload.user_key)
        if procedure:
            pending = PendingAppointmentSelection(
                user_key=payload.user_key,
                channel=payload.channel,
                procedure=procedure,
                places=[],
            )
            appointment_selection_store.save(pending)
            was_just_loaded = True
        else:
            return None

    if mentions_crc(payload.text):
        pending.mentioned_crc = True

    # Resolve procedure when user was asked for tecnomecanica / licencia / curso.
    if pending.procedure in {"", AWAITING_PROCEDURE}:
        resolved = procedure_for_text(payload.text)
        if resolved is None:
            appointment_selection_store.save(pending)
            return AgentTurnResponse(
                text="Claro. Dime si la cita es para tecnomecanica, licencia o curso por multa.",
                state_version=1,
                mode="appointment_missing_procedure",
            )
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

    if wants_alternative_places(payload.text):
        return AgentTurnResponse(
            text=format_place_options_response(pending.places, starts_at=pending.starts_at),
            state_version=1,
            mode="appointment_place_options",
            tool_calls=[],
        )

    selection_idx = extract_place_selection(payload.text, places=pending.places)
    if selection_idx is None and _looks_like_place_confirmation(payload.text):
        if pending.selected_index is not None:
            selection_idx = pending.selected_index
        elif len(pending.places) == 1:
            selection_idx = 1

    if selection_idx is not None:
        if not (1 <= selection_idx <= len(pending.places)):
            return AgentTurnResponse(
                text=f"Elige una opcion entre 1 y {len(pending.places)}.",
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
        return None

    place = pending.places[pending.selected_index - 1]
    try:
        appointment_data = await AppointmentClient().create(
            user_key=payload.user_key,
            procedure=pending.procedure,
            starts_at=pending.starts_at,
            place=place,
            notification_to=notification_to_for_turn(payload),
        )
        appointment_selection_store.clear(user_key=payload.user_key, channel=payload.channel)
        tool_calls = ["appointment.select_place", "appointment.create"]
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
            text="Tuve un problema creando la cita. Intentalo de nuevo en un momento.",
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
            text="Tuve un problema buscando centros cercanos. Intentalo de nuevo en un momento.",
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
        return AgentTurnResponse(
            text=crc_note + format_no_affiliate_coverage(),
            state_version=1,
            mode="places_empty",
            tool_calls=["places.find_nearest"],
        )

    if len(places) > 1:
        appointment_selection_store.save(
            PendingAppointmentSelection(
                user_key=payload.user_key,
                channel=payload.channel,
                procedure=procedure,
                places=[dict(place) for place in places],
                starts_at=starts_at,
                mentioned_crc=mentioned_crc,
            )
        )
        return AgentTurnResponse(
            text=crc_note + format_place_options_response(places, starts_at=starts_at),
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
                places=[dict(places[0])],
                mentioned_crc=mentioned_crc,
            )
        )
        return AgentTurnResponse(
            text=crc_note + format_place_response(places[0]),
            state_version=1,
            mode="places_suggested",
            tool_calls=["places.find_nearest"],
        )

    try:
        appointment_data = await AppointmentClient().create(
            user_key=payload.user_key,
            procedure=procedure,
            starts_at=starts_at,
            place=places[0],
            notification_to=notification_to_for_turn(payload),
        )
        appointment_selection_store.clear(user_key=payload.user_key, channel=payload.channel)
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
            text="Tuve un problema creando la cita. Intentalo de nuevo en un momento.",
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
    try:
        result = await provider.complete(
            system_prompt=build_system_prompt(),
            user_text=user_text_override or payload.text,
            user_key=payload.user_key,
            channel=payload.channel,
        )
    except httpx.HTTPStatusError:
        return AgentTurnResponse(
            text="Tuve un problema procesando tu mensaje. Intentalo de nuevo en un momento.",
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
    "Dale. Para buscarte el centro mas cercano necesito tu ubicacion. Puedes mandarme tu ubicacion "
    "por WhatsApp o escribirme la ciudad/direccion donde quieres agendar."
)

LOCATION_REQUEST_PENDING_TEXT = (
    "Ya tengo el tramite. Ahora comparteme tu ubicacion por WhatsApp o dime la ciudad para buscar centros cercanos."
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


def location_for_turn(payload: AgentTurnRequest) -> tuple[float, float] | None:
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
                    text="Tu consulta ya esta en proceso. En un momento te mando el resultado.",
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
            text="Hay muchas consultas en curso. Intentalo de nuevo en un momento.",
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
            city_bit = f" en *{ciudad}*" if ciudad else ""
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
