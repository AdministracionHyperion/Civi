from __future__ import annotations

import os
import re
import unicodedata

from civi_common.events import EventPublisher, event_publisher_from_env
from conversation_service.adapters.outbound.agent_client import AgentClient, HttpAgentClient
from conversation_service.shared.repository import ConversationRepository, repository
from conversation_service.slices.classify_consent.use_case import ConsentClassifier, classify_consent

from .schemas import RunTurnRequest, RunTurnResponse

GREETING_HABEAS_DATA_TEXT = (
    "Hola 👋 Soy *Civi*, tu asistente para tramites de transito en Colombia: "
    "SOAT, tecnomecanica, licencias y cursos por comparendo.\n\n"
    "Para orientarte necesito tu autorizacion para tratar tus datos personales "
    "segun la Ley 1581 de 2012 (Habeas Data). Solo guardare lo necesario para ayudarte "
    "con el tramite.\n\n"
    "Responde *si* si autorizas o *no* si prefieres no continuar."
)

CONSENT_ACCEPTED_TEXT = (
    "Gracias. Ya registre tu consentimiento. En que te puedo ayudar hoy: SOAT, "
    "tecnomecanica, licencia o curso por multa?"
)

CONSENT_DECLINED_TEXT = (
    "Entendido. Sin consentimiento no puedo procesar datos personales ni continuar el flujo. "
    "Si cambias de opinion, responde *acepto*."
)

CONSENT_AMBIGUOUS_REASK_TEXT = (
    "No te entendi. Para continuar, autorizas el tratamiento de tus datos personales? "
    "Responde *si* o *no*."
)

CONSENT_QUESTION_EXPLAIN_TEXT = (
    "Solo guardo los datos necesarios para tu tramite, como placa, cedula, ciudad, cita y canal de contacto. "
    "Puedes pedir que borremos tus datos cuando quieras. Autorizas el tratamiento de datos? Responde *si* o *no*."
)

CONTROL_HARD_RESET_TEXT = (
    "Listo, deje esta conversacion en cero para pruebas: borre el historial y el consentimiento de este canal. "
    "Escribe *hola* para empezar otra vez desde Habeas Data."
)

CONTROL_SOFT_RESET_TEXT = (
    "Listo, borre el historial de esta conversacion y conserve el consentimiento. "
    "Puedes seguir probando desde el flujo actual."
)

HARD_RESET_COMMANDS = {
    "reset",
    "reiniciar",
    "empezar de nuevo",
    "volver a empezar",
    "forget",
    "olvidar",
    "olvidar todo",
}

SOFT_RESET_COMMANDS = {
    "reset-soft",
    "soft-reset",
    "reset suave",
    "reinicio suave",
}

STATUS_COMMANDS = {"estado", "status"}


async def run_turn(
    payload: RunTurnRequest,
    *,
    agent_client: AgentClient | None = None,
    consent_classifier: ConsentClassifier | None = None,
    conversation_repository: ConversationRepository | None = None,
    event_publisher: EventPublisher | None = None,
) -> RunTurnResponse:
    active_repository = conversation_repository or repository
    publisher = event_publisher or event_publisher_from_env()

    control_response = await _maybe_handle_control_command(
        payload,
        repository=active_repository,
        publisher=publisher,
    )
    if control_response is not None:
        return control_response

    consent_response = await _maybe_handle_consent(
        payload,
        repository=active_repository,
        publisher=publisher,
        consent_classifier=consent_classifier,
    )
    if consent_response is not None:
        return consent_response

    data = await (agent_client or HttpAgentClient()).run_turn(payload)
    state_version = data.get("state_version", 1)
    text = data["text"]

    active_repository.record_turn(
        user_key=payload.user_key,
        channel=payload.channel,
        user_text=payload.text,
        agent_text=text,
        state_version=state_version,
    )
    await _publish_conversation_completed(
        publisher,
        user_key=payload.user_key,
        channel=payload.channel,
        state_version=state_version,
    )

    return RunTurnResponse(
        user_key=payload.user_key,
        text=text,
        state_version=state_version,
    )


async def _maybe_handle_control_command(
    payload: RunTurnRequest,
    *,
    repository: ConversationRepository,
    publisher: EventPublisher,
) -> RunTurnResponse | None:
    command = _control_command_for_text(payload.text)
    if command is None:
        return None

    if command == "hard_reset":
        repository.clear_history(user_key=payload.user_key, channel=payload.channel)
        repository.clear_consent(user_key=payload.user_key, channel=payload.channel)
        response_text = CONTROL_HARD_RESET_TEXT
    elif command == "soft_reset":
        repository.clear_history(user_key=payload.user_key, channel=payload.channel)
        response_text = CONTROL_SOFT_RESET_TEXT
    else:
        response_text = _status_text(payload, repository=repository)

    await _publish_conversation_completed(
        publisher,
        user_key=payload.user_key,
        channel=payload.channel,
        state_version=0,
    )
    return RunTurnResponse(user_key=payload.user_key, text=response_text, state_version=0)


async def _maybe_handle_consent(
    payload: RunTurnRequest,
    *,
    repository: ConversationRepository,
    publisher: EventPublisher,
    consent_classifier: ConsentClassifier | None,
) -> RunTurnResponse | None:
    consent = repository.get_consent(user_key=payload.user_key, channel=payload.channel)
    if consent is not None and consent.status == "accepted":
        return None

    normalized = _normalize(payload.text)
    stripped_for_accept = _strip_negated_affirmations(normalized)
    if _is_decline(normalized):
        return await _record_consent_status(
            payload,
            repository=repository,
            publisher=publisher,
            status="declined",
            response_text=CONSENT_DECLINED_TEXT,
            redacted_user_text="[consent_declined]",
        )
    if _is_accept(stripped_for_accept):
        return await _record_consent_status(
            payload,
            repository=repository,
            publisher=publisher,
            status="accepted",
            response_text=CONSENT_ACCEPTED_TEXT,
            redacted_user_text="[consent_accepted]",
        )

    llm_classification = None
    if _should_use_consent_classifier(normalized):
        llm_classification = await classify_consent(
            text=payload.text,
            user_key=payload.user_key,
            channel=payload.channel,
            classifier=consent_classifier,
        )
        if llm_classification == "DECLINE":
            return await _record_consent_status(
                payload,
                repository=repository,
                publisher=publisher,
                status="declined",
                response_text=CONSENT_DECLINED_TEXT,
                redacted_user_text="[consent_declined]",
            )
        if llm_classification == "ACCEPT":
            return await _record_consent_status(
                payload,
                repository=repository,
                publisher=publisher,
                status="accepted",
                response_text=CONSENT_ACCEPTED_TEXT,
                redacted_user_text="[consent_accepted]",
            )

    if _is_consent_question(normalized) or llm_classification == "QUESTION":
        response_text = CONSENT_QUESTION_EXPLAIN_TEXT
    elif llm_classification == "AMBIGUOUS":
        response_text = CONSENT_AMBIGUOUS_REASK_TEXT
    elif consent is None:
        response_text = GREETING_HABEAS_DATA_TEXT
    else:
        response_text = CONSENT_AMBIGUOUS_REASK_TEXT

    repository.record_turn(
        user_key=payload.user_key,
        channel=payload.channel,
        user_text="[consent_pending_message_redacted]",
        agent_text=response_text,
        state_version=1,
    )
    await _publish_conversation_completed(
        publisher,
        user_key=payload.user_key,
        channel=payload.channel,
        state_version=1,
    )
    return RunTurnResponse(user_key=payload.user_key, text=response_text, state_version=1)


async def _record_consent_status(
    payload: RunTurnRequest,
    *,
    repository: ConversationRepository,
    publisher: EventPublisher,
    status: str,
    response_text: str,
    redacted_user_text: str,
) -> RunTurnResponse:
    record = repository.set_consent(
        user_key=payload.user_key,
        channel=payload.channel,
        status=status,
        purpose="civi_conversation",
        policy_version=os.getenv("CONSENT_POLICY_VERSION", "2026-07-07"),
    )
    await publisher.publish(
        "consent.updated",
        {
            "user_key": record.user_key,
            "channel": record.channel,
            "status": record.status,
            "purpose": record.purpose,
            "policy_version": record.policy_version,
        },
        producer="conversation-service",
    )
    repository.record_turn(
        user_key=payload.user_key,
        channel=payload.channel,
        user_text=redacted_user_text,
        agent_text=response_text,
        state_version=1,
    )
    await _publish_conversation_completed(
        publisher,
        user_key=payload.user_key,
        channel=payload.channel,
        state_version=1,
    )
    return RunTurnResponse(user_key=payload.user_key, text=response_text, state_version=1)


async def _publish_conversation_completed(
    publisher: EventPublisher,
    *,
    user_key: str,
    channel: str,
    state_version: int,
) -> None:
    await publisher.publish(
        "conversation.completed",
        {
            "user_key": user_key,
            "channel": channel,
            "state_version": state_version,
        },
        producer="conversation-service",
    )


def _normalize(value: str) -> str:
    normalized = unicodedata.normalize("NFKD", value or "")
    without_accents = "".join(char for char in normalized if not unicodedata.combining(char))
    collapsed = " ".join(without_accents.lower().strip().split())
    return re.sub(r"[!?\.,;:]", "", collapsed).strip()


def _control_command_for_text(value: str) -> str | None:
    normalized = _normalize(value).lstrip("/").replace("_", "-")
    if normalized in HARD_RESET_COMMANDS:
        return "hard_reset"
    if normalized in SOFT_RESET_COMMANDS:
        return "soft_reset"
    if normalized in STATUS_COMMANDS:
        return "status"
    return None


def _status_text(payload: RunTurnRequest, *, repository: ConversationRepository) -> str:
    consent = repository.get_consent(user_key=payload.user_key, channel=payload.channel)
    consent_label = _consent_status_label(consent.status if consent else None)
    history_count = repository.count_for_user(user_key=payload.user_key, channel=payload.channel)
    return (
        "Estado de pruebas para este canal: "
        f"consentimiento *{consent_label}*; turnos guardados: *{history_count}*."
    )


def _consent_status_label(status: str | None) -> str:
    if status == "accepted":
        return "aceptado"
    if status == "declined":
        return "rechazado"
    return "sin registrar"


NEGATED_AFFIRMATION_PATTERN = re.compile(
    r"\b(no|nunca|jamas|tampoco)\s+"
    r"(acept\w*|autoriz\w*|permit\w*|quier\w*|si|dale|va|vale|ok|listo|bueno)\b"
)


def _strip_negated_affirmations(normalized_text: str) -> str:
    return NEGATED_AFFIRMATION_PATTERN.sub(" ", normalized_text).strip()


DECLINE_PHRASES: tuple[str, ...] = (
    "no acepto",
    "no autorizo",
    "no permito",
    "no quiero",
    "no gracias",
    "rechazo",
    "declino",
    "mejor no",
    "paso",
    "nope",
)

DECLINE_EXACT = {"no"}


def _is_decline(normalized_text: str) -> bool:
    if not normalized_text:
        return False
    if normalized_text in DECLINE_EXACT:
        return True
    return any(phrase in normalized_text for phrase in DECLINE_PHRASES)


ACCEPT_PHRASES: tuple[str, ...] = (
    "acepto",
    "autorizo",
    "permito",
    "de acuerdo",
    "si acepto",
    "si autorizo",
    "claro que si",
    "por supuesto",
    "hagale",
    "de una",
    "proceda",
    "adelante",
    "esta bien",
    "todo bien",
    "listo",
    "perfecto",
    "sigamos",
)

ACCEPT_EXACT = {"si", "sip", "s", "dale", "va", "vale", "bueno", "ok", "okay", "claro"}


def _is_accept(normalized_text: str) -> bool:
    if not normalized_text:
        return False
    if normalized_text in ACCEPT_EXACT:
        return True
    return any(phrase in normalized_text for phrase in ACCEPT_PHRASES)


CONSENT_CLASSIFIER_HINTS: tuple[str, ...] = (
    "acept",
    "autor",
    "permit",
    "consent",
    "datos",
    "habeas",
    "privacidad",
    "tratamiento",
    "explic",
    "si",
    "bueno",
    "dale",
    "listo",
    "creo",
    "pues",
    "hagamos",
    "hagamole",
    "de pronto",
    "tal vez",
)


def _should_use_consent_classifier(normalized_text: str) -> bool:
    if not normalized_text:
        return False
    if _is_consent_question(normalized_text):
        return False
    return any(hint in normalized_text for hint in CONSENT_CLASSIFIER_HINTS)


CONSENT_QUESTION_TERMS: tuple[str, ...] = (
    "que datos",
    "cuales datos",
    "para que",
    "por que",
    "porque",
    "habeas",
    "privacidad",
    "politica",
    "tratamiento",
    "borrar mis datos",
    "eliminar mis datos",
)


def _is_consent_question(normalized_text: str) -> bool:
    return any(term in normalized_text for term in CONSENT_QUESTION_TERMS)
