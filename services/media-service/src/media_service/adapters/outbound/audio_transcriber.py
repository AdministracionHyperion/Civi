from __future__ import annotations

import os
from typing import Protocol

import httpx


class AudioTranscriber(Protocol):
    async def transcribe(self, *, media_ref: str, content_type: str) -> dict[str, object]:
        ...


class DisabledAudioTranscriber:
    async def transcribe(self, *, media_ref: str, content_type: str) -> dict[str, object]:
        return {
            "provider_mode": "disabled_until_provider_configured",
            "transcript": None,
        }


class OpenAIUrlAudioTranscriber:
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
            raise RuntimeError("OPENAI_API_KEY and OPENAI_AUDIO_TRANSCRIPTION_MODEL are required")

    async def transcribe(self, *, media_ref: str, content_type: str) -> dict[str, object]:
        if not media_ref.startswith(("http://", "https://")):
            raise RuntimeError("OpenAI audio transcription requires media_ref to be an HTTP(S) URL")

        async with httpx.AsyncClient(timeout=60.0, transport=self.transport) as client:
            media_response = await client.get(media_ref)
            media_response.raise_for_status()
            transcription_response = await client.post(
                f"{self.base_url}/v1/audio/transcriptions",
                headers={"Authorization": f"Bearer {self.api_key}"},
                data={"model": self.model},
                files={"file": ("audio", media_response.content, content_type)},
            )
            transcription_response.raise_for_status()
            data = transcription_response.json()
        return {
            "provider_mode": "openai",
            "transcript": data.get("text"),
        }


def audio_transcriber_from_env() -> AudioTranscriber:
    mode = os.getenv("MEDIA_AUDIO_PROVIDER_MODE", "disabled").strip().lower()
    if mode in {"", "disabled"}:
        return DisabledAudioTranscriber()
    if mode == "openai":
        return OpenAIUrlAudioTranscriber(
            api_key=os.getenv("OPENAI_API_KEY", ""),
            model=os.getenv("OPENAI_AUDIO_TRANSCRIPTION_MODEL", ""),
            base_url=os.getenv("OPENAI_BASE_URL", "https://api.openai.com"),
        )
    raise RuntimeError(f"unsupported audio provider mode: {mode}")
