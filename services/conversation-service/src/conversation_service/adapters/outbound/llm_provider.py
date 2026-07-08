from __future__ import annotations

import os
from typing import Protocol

import httpx


class LLMProvider(Protocol):
    async def complete(
        self,
        *,
        system_prompt: str,
        user_text: str,
        user_key: str,
        channel: str,
    ) -> dict[str, object]:
        ...


class DisabledLLMProvider:
    async def complete(
        self,
        *,
        system_prompt: str,
        user_text: str,
        user_key: str,
        channel: str,
    ) -> dict[str, object]:
        return {"provider_mode": "disabled_until_provider_configured", "text": None}


class OpenAIResponsesLLMProvider:
    def __init__(
        self,
        *,
        api_key: str,
        model: str,
        base_url: str = "https://api.openai.com",
        transport: httpx.AsyncBaseTransport | None = None,
    ) -> None:
        self.api_key = api_key.strip()
        self.model = model.strip()
        self.base_url = base_url.rstrip("/")
        self.transport = transport
        if not self.api_key or not self.model:
            raise RuntimeError("OPENAI_API_KEY and OPENAI_LLM_MODEL are required")

    async def complete(
        self,
        *,
        system_prompt: str,
        user_text: str,
        user_key: str,
        channel: str,
    ) -> dict[str, object]:
        payload = {
            "model": self.model,
            "instructions": system_prompt,
            "input": user_text,
            "store": False,
            "metadata": {
                "service": "conversation-service",
                "channel": channel,
            },
        }
        async with httpx.AsyncClient(timeout=20.0, transport=self.transport) as client:
            response = await client.post(
                f"{self.base_url}/v1/responses",
                json=payload,
                headers={"Authorization": f"Bearer {self.api_key}"},
            )
            response.raise_for_status()
            data = response.json()
        return {
            "provider_mode": "openai-responses",
            "text": _extract_response_text(data),
            "response_id": data.get("id"),
        }


class OpenAICompatibleChatLLMProvider:
    def __init__(
        self,
        *,
        provider_mode: str,
        api_key: str,
        model: str,
        base_url: str,
        transport: httpx.AsyncBaseTransport | None = None,
    ) -> None:
        self.provider_mode = provider_mode.strip().lower()
        self.api_key = api_key.strip()
        self.model = model.strip()
        self.base_url = base_url.rstrip("/")
        self.transport = transport
        if not self.provider_mode or not self.api_key or not self.model or not self.base_url:
            raise RuntimeError(f"{provider_mode.upper()} API key, model and base URL are required")

    async def complete(
        self,
        *,
        system_prompt: str,
        user_text: str,
        user_key: str,
        channel: str,
    ) -> dict[str, object]:
        payload = {
            "model": self.model,
            "messages": [
                {"role": "system", "content": system_prompt},
                {"role": "user", "content": user_text},
            ],
        }
        async with httpx.AsyncClient(timeout=20.0, transport=self.transport) as client:
            response = await client.post(
                f"{self.base_url}/chat/completions",
                json=payload,
                headers={"Authorization": f"Bearer {self.api_key}"},
            )
            response.raise_for_status()
            data = response.json()
        return {
            "provider_mode": self.provider_mode,
            "text": _extract_chat_completion_text(data),
            "response_id": data.get("id"),
        }


def llm_provider_from_env() -> LLMProvider:
    mode = os.getenv("LLM_PROVIDER_MODE", os.getenv("LLM_PROVIDER", "disabled")).strip().lower()
    if mode in {"", "disabled"}:
        return DisabledLLMProvider()
    if mode == "openai":
        return OpenAIResponsesLLMProvider(
            api_key=os.getenv("OPENAI_API_KEY", ""),
            model=os.getenv("OPENAI_LLM_MODEL", os.getenv("OPENAI_MODEL", "")),
            base_url=os.getenv("OPENAI_BASE_URL", "https://api.openai.com"),
        )
    if mode == "deepseek":
        return OpenAICompatibleChatLLMProvider(
            provider_mode="deepseek",
            api_key=os.getenv("DEEPSEEK_API_KEY", ""),
            model=os.getenv("DEEPSEEK_MODEL", "deepseek-chat"),
            base_url=os.getenv("DEEPSEEK_BASE_URL", "https://api.deepseek.com/v1"),
        )
    if mode == "groq":
        return OpenAICompatibleChatLLMProvider(
            provider_mode="groq",
            api_key=os.getenv("GROQ_API_KEY", ""),
            model=os.getenv("GROQ_MODEL", "llama-3.3-70b-versatile"),
            base_url=os.getenv("GROQ_BASE_URL", "https://api.groq.com/openai/v1"),
        )
    raise RuntimeError(f"unsupported LLM provider mode: {mode}")


def _extract_response_text(data: dict[str, object]) -> str | None:
    direct = data.get("output_text")
    if isinstance(direct, str) and direct.strip():
        return direct.strip()

    output = data.get("output")
    if not isinstance(output, list):
        return None
    parts: list[str] = []
    for item in output:
        if not isinstance(item, dict):
            continue
        content = item.get("content")
        if not isinstance(content, list):
            continue
        for content_item in content:
            if isinstance(content_item, dict) and isinstance(content_item.get("text"), str):
                parts.append(content_item["text"])
    text = "\n".join(parts).strip()
    return text or None


def _extract_chat_completion_text(data: dict[str, object]) -> str | None:
    choices = data.get("choices")
    if not isinstance(choices, list) or not choices:
        return None
    first = choices[0]
    if not isinstance(first, dict):
        return None
    message = first.get("message")
    if not isinstance(message, dict):
        return None
    content = message.get("content")
    if isinstance(content, str):
        return content.strip() or None
    return None
