from __future__ import annotations

import os
from typing import Any

import httpx


class WhatsAppMediaDownloadError(RuntimeError):
    """Raised when Meta media metadata or bytes cannot be downloaded."""


class WhatsAppMediaClient:
    def __init__(
        self,
        *,
        access_token: str | None = None,
        api_version: str | None = None,
        base_url: str = "https://graph.facebook.com",
        transport: httpx.AsyncBaseTransport | None = None,
    ) -> None:
        self.access_token = (access_token if access_token is not None else os.getenv("WHATSAPP_ACCESS_TOKEN", "")).strip()
        self.api_version = (
            api_version if api_version is not None else os.getenv("WHATSAPP_GRAPH_API_VERSION", "v20.0")
        ).strip() or "v20.0"
        self.base_url = base_url.rstrip("/")
        self.transport = transport
        if not self.access_token:
            raise RuntimeError("WHATSAPP_ACCESS_TOKEN is required to download WhatsApp media")

    @classmethod
    def from_env(cls) -> "WhatsAppMediaClient":
        return cls()

    async def download(self, media_id: str) -> dict[str, Any]:
        media_id = str(media_id or "").strip()
        if not media_id:
            raise WhatsAppMediaDownloadError("missing WhatsApp media id")

        headers = {"Authorization": f"Bearer {self.access_token}"}
        async with httpx.AsyncClient(timeout=60.0, transport=self.transport) as client:
            meta_response = await client.get(
                f"{self.base_url}/{self.api_version}/{media_id}",
                headers=headers,
            )
            try:
                meta_response.raise_for_status()
            except httpx.HTTPError as exc:
                raise WhatsAppMediaDownloadError(f"failed to resolve WhatsApp media {media_id}") from exc

            meta = meta_response.json()
            if not isinstance(meta, dict):
                raise WhatsAppMediaDownloadError("invalid WhatsApp media metadata")
            download_url = str(meta.get("url") or "").strip()
            content_type = str(meta.get("mime_type") or meta.get("mimeType") or "").strip()
            if not download_url:
                raise WhatsAppMediaDownloadError("WhatsApp media metadata missing url")

            media_response = await client.get(download_url, headers=headers)
            try:
                media_response.raise_for_status()
            except httpx.HTTPError as exc:
                raise WhatsAppMediaDownloadError(f"failed to download WhatsApp media {media_id}") from exc

            content = media_response.content
            if not content:
                raise WhatsAppMediaDownloadError("WhatsApp media download returned empty body")

            resolved_type = content_type or str(media_response.headers.get("content-type") or "").strip()
            return {
                "media_id": media_id,
                "content_type": resolved_type,
                "size_bytes": len(content),
                "content": content,
            }
