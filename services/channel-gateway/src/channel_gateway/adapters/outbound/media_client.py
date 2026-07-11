from __future__ import annotations

import base64
import os
from typing import Any

import httpx


class MediaServiceError(RuntimeError):
    """Raised when media-service cannot process audio/image."""


class MediaClient:
    def __init__(
        self,
        *,
        base_url: str | None = None,
        token: str | None = None,
        transport: httpx.AsyncBaseTransport | None = None,
    ) -> None:
        self.base_url = (base_url or os.getenv("MEDIA_SERVICE_URL", "http://localhost:8088")).rstrip("/")
        self.token = (token if token is not None else os.getenv("INTERNAL_SERVICE_TOKEN", "")).strip()
        self.transport = transport
        if not self.token:
            raise RuntimeError("INTERNAL_SERVICE_TOKEN is required for media-service calls")

    @classmethod
    def from_env(cls) -> "MediaClient":
        return cls()

    @property
    def _headers(self) -> dict[str, str]:
        return {"Authorization": f"Bearer {self.token}"}

    async def process_audio(
        self,
        *,
        content_type: str,
        size_bytes: int,
        media_ref: str,
        content: bytes,
    ) -> dict[str, Any]:
        return await self._post(
            "/internal/media/audio",
            {
                "content_type": content_type,
                "size_bytes": size_bytes,
                "media_ref": media_ref,
                "content_base64": base64.b64encode(content).decode("ascii"),
            },
        )

    async def process_image(
        self,
        *,
        content_type: str,
        size_bytes: int,
        media_ref: str,
        content: bytes,
    ) -> dict[str, Any]:
        return await self._post(
            "/internal/media/image",
            {
                "content_type": content_type,
                "size_bytes": size_bytes,
                "media_ref": media_ref,
                "content_base64": base64.b64encode(content).decode("ascii"),
            },
        )

    async def _post(self, path: str, payload: dict[str, Any]) -> dict[str, Any]:
        async with httpx.AsyncClient(timeout=90.0, transport=self.transport) as client:
            try:
                response = await client.post(
                    f"{self.base_url}{path}",
                    json=payload,
                    headers=self._headers,
                )
                response.raise_for_status()
            except httpx.HTTPError as exc:
                raise MediaServiceError(f"media-service call failed: {path}") from exc
            data = response.json()
            if not isinstance(data, dict):
                raise MediaServiceError("media-service returned a non-object payload")
            return data
