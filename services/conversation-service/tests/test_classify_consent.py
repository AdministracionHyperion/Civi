from __future__ import annotations

import httpx
import pytest

from conversation_service.slices.classify_consent.use_case import LLMConsentClassifier, classify_consent


class FakeLLMProvider:
    def __init__(self, text: str | None) -> None:
        self.text = text
        self.calls = 0
        self.payloads: list[dict[str, str]] = []

    async def complete(
        self,
        *,
        system_prompt: str,
        user_text: str,
        user_key: str,
        channel: str,
    ) -> dict[str, object]:
        self.calls += 1
        self.payloads.append(
            {
                "system_prompt": system_prompt,
                "user_text": user_text,
                "user_key": user_key,
                "channel": channel,
            }
        )
        return {"text": self.text}


class FailingLLMProvider:
    async def complete(
        self,
        *,
        system_prompt: str,
        user_text: str,
        user_key: str,
        channel: str,
    ) -> dict[str, object]:
        raise httpx.ConnectError("provider unavailable")


@pytest.mark.asyncio
@pytest.mark.parametrize(
    ("provider_text", "expected"),
    [
        ("ACCEPT", "ACCEPT"),
        ("DECLINE", "DECLINE"),
        ("QUESTION", "QUESTION"),
        ("AMBIGUOUS", "AMBIGUOUS"),
        ("Classification: ACCEPT", "ACCEPT"),
        ("no idea", "AMBIGUOUS"),
    ],
)
async def test_llm_consent_classifier_parses_closed_labels(provider_text: str, expected: str) -> None:
    provider = FakeLLMProvider(provider_text)
    classifier = LLMConsentClassifier(provider=provider)

    result = await classifier.classify(text="creo que si", user_key="user-consent", channel="web")

    assert result == expected
    assert provider.calls == 1


@pytest.mark.asyncio
async def test_llm_consent_classifier_redacts_sensitive_values_before_provider() -> None:
    provider = FakeLLMProvider("QUESTION")
    classifier = LLMConsentClassifier(provider=provider)

    result = await classifier.classify(
        text="Mi cedula es 123456789 y mi correo es persona@example.com, pero explicame",
        user_key="user-consent",
        channel="whatsapp",
    )

    sent_text = provider.payloads[0]["user_text"]

    assert result == "QUESTION"
    assert "123456789" not in sent_text
    assert "persona@example.com" not in sent_text
    assert "[numero]" in sent_text
    assert "[email]" in sent_text


@pytest.mark.asyncio
async def test_classify_consent_falls_back_to_ambiguous_when_provider_fails() -> None:
    classifier = LLMConsentClassifier(provider=FailingLLMProvider())

    result = await classify_consent(
        text="pues bueno",
        user_key="user-consent",
        channel="web",
        classifier=classifier,
    )

    assert result == "AMBIGUOUS"
