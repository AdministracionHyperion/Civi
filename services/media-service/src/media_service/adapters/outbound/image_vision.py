from __future__ import annotations

import base64
import os
from typing import Protocol

import httpx

from media_service.shared.policy import normalize_content_type

DEFAULT_IMAGE_VISION_PROMPT = (
    "Describe brevemente qué se ve en la imagen (objetos, situación y detalles relevantes). "
    "Si hay texto visible, inclúyelo literalmente. Responde en español, en pocas oraciones."
)


class ImageVisionExtractor(Protocol):
    async def extract_text(
        self,
        *,
        media_ref: str,
        content_type: str,
        content_base64: str | None = None,
    ) -> dict[str, object]:
        ...


class DisabledImageVisionExtractor:
    async def extract_text(
        self,
        *,
        media_ref: str,
        content_type: str,
        content_base64: str | None = None,
    ) -> dict[str, object]:
        return {
            "provider_mode": "disabled_until_provider_configured",
            "extracted_text": None,
        }


class OpenAIImageVisionExtractor:
    def __init__(
        self,
        *,
        api_key: str,
        model: str,
        prompt: str = DEFAULT_IMAGE_VISION_PROMPT,
        base_url: str = "https://api.openai.com",
        transport: httpx.AsyncBaseTransport | None = None,
    ) -> None:
        self.api_key = api_key.strip()
        self.model = model.strip()
        self.prompt = prompt
        self.base_url = base_url.rstrip("/")
        self.transport = transport
        if not self.api_key or not self.model:
            raise RuntimeError("OPENAI_API_KEY and OPENAI_IMAGE_VISION_MODEL are required")

    async def extract_text(
        self,
        *,
        media_ref: str,
        content_type: str,
        content_base64: str | None = None,
    ) -> dict[str, object]:
        image_url = _image_url_for_request(media_ref=media_ref, content_type=content_type, content_base64=content_base64)
        payload = {
            "model": self.model,
            "input": [
                {
                    "role": "user",
                    "content": [
                        {"type": "input_text", "text": self.prompt},
                        {"type": "input_image", "image_url": image_url},
                    ],
                }
            ],
        }
        async with httpx.AsyncClient(timeout=60.0, transport=self.transport) as client:
            response = await client.post(
                f"{self.base_url}/v1/responses",
                json=payload,
                headers={"Authorization": f"Bearer {self.api_key}"},
            )
            response.raise_for_status()
            data = response.json()
        return {
            "provider_mode": "openai",
            "extracted_text": _extract_response_text(data),
        }


class OpenAICompatibleImageVisionExtractor:
    def __init__(
        self,
        *,
        provider_mode: str,
        api_key: str,
        model: str,
        base_url: str,
        prompt: str = DEFAULT_IMAGE_VISION_PROMPT,
        transport: httpx.AsyncBaseTransport | None = None,
    ) -> None:
        self.provider_mode = provider_mode.strip().lower()
        self.api_key = api_key.strip()
        self.model = model.strip()
        self.base_url = base_url.rstrip("/")
        self.prompt = prompt
        self.transport = transport
        if not self.provider_mode or not self.api_key or not self.model or not self.base_url:
            raise RuntimeError(f"{provider_mode.upper()} image API key, model and base URL are required")

    async def extract_text(
        self,
        *,
        media_ref: str,
        content_type: str,
        content_base64: str | None = None,
    ) -> dict[str, object]:
        image_url = _image_url_for_request(media_ref=media_ref, content_type=content_type, content_base64=content_base64)
        payload = {
            "model": self.model,
            "messages": [
                {
                    "role": "user",
                    "content": [
                        {"type": "text", "text": self.prompt},
                        {"type": "image_url", "image_url": {"url": image_url}},
                    ],
                }
            ],
        }
        async with httpx.AsyncClient(timeout=60.0, transport=self.transport) as client:
            response = await client.post(
                f"{self.base_url}/chat/completions",
                json=payload,
                headers={"Authorization": f"Bearer {self.api_key}"},
            )
            response.raise_for_status()
            data = response.json()
        return {
            "provider_mode": self.provider_mode,
            "extracted_text": _extract_chat_completion_text(data),
        }


def image_vision_from_env() -> ImageVisionExtractor:
    mode = os.getenv("MEDIA_IMAGE_PROVIDER_MODE", "disabled").strip().lower()
    if mode in {"", "disabled"}:
        return DisabledImageVisionExtractor()
    prompt = os.getenv("OPENAI_IMAGE_EXTRACTION_PROMPT", DEFAULT_IMAGE_VISION_PROMPT).strip() or DEFAULT_IMAGE_VISION_PROMPT
    if mode == "openai":
        return OpenAIImageVisionExtractor(
            api_key=os.getenv("OPENAI_API_KEY", ""),
            model=os.getenv("OPENAI_IMAGE_VISION_MODEL", ""),
            prompt=prompt,
            base_url=os.getenv("OPENAI_BASE_URL", "https://api.openai.com"),
        )
    if mode == "deepseek":
        return OpenAICompatibleImageVisionExtractor(
            provider_mode="deepseek",
            api_key=os.getenv("DEEPSEEK_API_KEY", ""),
            model=os.getenv("DEEPSEEK_IMAGE_MODEL", os.getenv("DEEPSEEK_MODEL", "deepseek-chat")),
            prompt=prompt,
            base_url=os.getenv("DEEPSEEK_BASE_URL", "https://api.deepseek.com/v1"),
        )
    if mode == "groq":
        return OpenAICompatibleImageVisionExtractor(
            provider_mode="groq",
            api_key=os.getenv("GROQ_API_KEY", ""),
            model=os.getenv("GROQ_IMAGE_MODEL", os.getenv("GROQ_MODEL", "")),
            prompt=prompt,
            base_url=os.getenv("GROQ_BASE_URL", "https://api.groq.com/openai/v1"),
        )
    raise RuntimeError(f"unsupported image provider mode: {mode}")


def _image_url_for_request(*, media_ref: str, content_type: str, content_base64: str | None) -> str:
    if content_base64:
        mime = normalize_content_type(content_type) or "image/jpeg"
        raw = content_base64.strip()
        if raw.lower().startswith("data:"):
            return raw
        # Normalize padding/whitespace for data URL.
        try:
            base64.b64decode(raw, validate=False)
        except Exception as exc:
            raise RuntimeError("invalid content_base64 for image extraction") from exc
        return f"data:{mime};base64,{raw}"
    if media_ref.startswith(("http://", "https://")):
        return media_ref
    raise RuntimeError("image extraction requires media_ref HTTP(S) URL or content_base64")


def _extract_response_text(data: dict[str, object]) -> str | None:
    direct = data.get("output_text")
    if isinstance(direct, str):
        return direct

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
    return "\n".join(parts) if parts else None


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
