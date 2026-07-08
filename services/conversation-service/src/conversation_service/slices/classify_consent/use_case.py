from __future__ import annotations

import logging
import re
from typing import Protocol, cast

import httpx

from conversation_service.adapters.outbound.llm_provider import LLMProvider, llm_provider_from_env

from .schemas import ConsentClassification, VALID_CONSENT_CLASSIFICATIONS

logger = logging.getLogger(__name__)

CONSENT_CLASSIFICATION_PROMPT = """Clasifica la respuesta del usuario al consentimiento de Habeas Data.

Devuelve exactamente una etiqueta:
ACCEPT: el usuario autoriza tratar sus datos.
DECLINE: el usuario no autoriza.
QUESTION: el usuario pregunta por privacidad, datos, Habeas Data o tratamiento.
AMBIGUOUS: no hay una decision clara.

No expliques. No agregues texto. Solo una etiqueta."""


class ConsentClassifier(Protocol):
    async def classify(
        self,
        *,
        text: str,
        user_key: str,
        channel: str,
    ) -> ConsentClassification:
        ...


class LLMConsentClassifier:
    def __init__(self, *, provider: LLMProvider | None = None) -> None:
        self.provider = provider or llm_provider_from_env()

    async def classify(
        self,
        *,
        text: str,
        user_key: str,
        channel: str,
    ) -> ConsentClassification:
        result = await self.provider.complete(
            system_prompt=CONSENT_CLASSIFICATION_PROMPT,
            user_text=_redact_for_classifier(text),
            user_key=user_key,
            channel=channel,
        )
        return _parse_classification(result.get("text"))


async def classify_consent(
    *,
    text: str,
    user_key: str,
    channel: str,
    classifier: ConsentClassifier | None = None,
) -> ConsentClassification:
    active_classifier = classifier or LLMConsentClassifier()
    try:
        return await active_classifier.classify(text=text, user_key=user_key, channel=channel)
    except (httpx.HTTPError, RuntimeError, ValueError) as exc:
        logger.warning("consent classification failed: %s", exc)
        return "AMBIGUOUS"


def _parse_classification(value: object) -> ConsentClassification:
    if not isinstance(value, str):
        return "AMBIGUOUS"

    cleaned = value.strip().upper()
    cleaned = cleaned.strip("`'\" .,:;")
    if cleaned in VALID_CONSENT_CLASSIFICATIONS:
        return cast(ConsentClassification, cleaned)

    matches = {label for label in VALID_CONSENT_CLASSIFICATIONS if re.search(rf"\b{label}\b", cleaned)}
    if len(matches) == 1:
        return cast(ConsentClassification, next(iter(matches)))
    return "AMBIGUOUS"


def _redact_for_classifier(value: str) -> str:
    text = value or ""
    text = re.sub(r"\b[\w.+-]+@[\w-]+(?:\.[\w-]+)+\b", "[email]", text)
    text = re.sub(r"\b\d{3,}\b", "[numero]", text)
    text = re.sub(r"\b[A-Z]{3}[-\s]?\d{2,3}[A-Z]?\b", "[placa]", text, flags=re.IGNORECASE)
    text = " ".join(text.strip().split())
    return text[:240]
