from __future__ import annotations

import hashlib
import hmac
import json
import logging
import os
from typing import Any

import httpx
from fastapi import APIRouter, BackgroundTasks, Depends, HTTPException, Query, Request, status
from fastapi.responses import PlainTextResponse

from civi_common import is_colombia_latlng
from channel_gateway.adapters.outbound.media_client import MediaClient, MediaServiceError
from channel_gateway.adapters.outbound.whatsapp_media import WhatsAppMediaClient, WhatsAppMediaDownloadError
from channel_gateway.shared.rate_limit import require_public_rate_limit
from channel_gateway.slices.receive_message.schemas import ReceiveMessageRequest
from channel_gateway.slices.receive_message.use_case import receive_message

router = APIRouter(tags=["whatsapp"])
logger = logging.getLogger(__name__)

MEDIA_PROCESS_FAILURE_REPLY = (
    "No pude procesar el audio o la imagen. Escribeme el mensaje o intentalo de nuevo."
)


@router.get("/webhook", response_class=PlainTextResponse)
@router.get("/webhook/whatsapp", response_class=PlainTextResponse)
async def verify_whatsapp_webhook(
    hub_mode: str = Query(alias="hub.mode"),
    hub_verify_token: str = Query(alias="hub.verify_token"),
    hub_challenge: str = Query(alias="hub.challenge"),
) -> PlainTextResponse:
    expected = os.getenv("WHATSAPP_VERIFY_TOKEN", "").strip()
    if not expected:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="WhatsApp verify token is not configured",
        )
    if hub_mode != "subscribe" or not hmac.compare_digest(hub_verify_token, expected):
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="invalid WhatsApp verify token")
    return PlainTextResponse(hub_challenge)


@router.post(
    "/webhook",
    status_code=202,
    dependencies=[Depends(require_public_rate_limit)],
)
@router.post(
    "/webhook/whatsapp",
    status_code=202,
    dependencies=[Depends(require_public_rate_limit)],
)
async def post_whatsapp_webhook(request: Request, background_tasks: BackgroundTasks) -> dict[str, object]:
    body = await request.body()
    _verify_signature_if_required(body, request.headers.get("X-Hub-Signature-256", ""))

    try:
        payload = json.loads(body.decode("utf-8") or "{}")
    except json.JSONDecodeError:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="invalid JSON body")

    inbound = await _extract_inbound_message(payload)
    if inbound is None:
        return {"success": True, "handled": False}

    direct_reply = str(inbound.get("direct_reply") or "").strip()
    if direct_reply:
        background_tasks.add_task(_send_whatsapp_reply, to=inbound["from"], body=direct_reply)
        return {
            "success": True,
            "handled": True,
            "user_key": inbound["from"],
            "source": "media_process_failure",
            "reply_scheduled": True,
        }

    response = await receive_message(
        ReceiveMessageRequest(
            user_key=inbound["from"],
            text=inbound["text"],
            channel="whatsapp",
            metadata=inbound.get("metadata", {}),
        )
    )
    background_tasks.add_task(_send_whatsapp_reply, to=inbound["from"], body=response.text)
    return {
        "success": True,
        "handled": True,
        "user_key": response.user_key,
        "source": response.source,
        "reply_scheduled": True,
    }


async def _send_whatsapp_reply(*, to: str, body: str) -> None:
    if not body.strip():
        return

    base_url = os.getenv("NOTIFICATION_SERVICE_URL", "http://localhost:8087").rstrip("/")
    token = os.getenv("INTERNAL_SERVICE_TOKEN", "").strip()
    if not token:
        logger.error("Cannot send WhatsApp reply because INTERNAL_SERVICE_TOKEN is not configured")
        return

    headers = {"Authorization": f"Bearer {token}"}
    try:
        async with httpx.AsyncClient(timeout=30.0) as client:
            queued = await client.post(
                f"{base_url}/internal/notifications/whatsapp",
                json={"to": to, "body": body},
                headers=headers,
            )
            queued.raise_for_status()

            if _bool_from_env("WHATSAPP_REPLY_DISPATCH_IMMEDIATE", True):
                dispatched = await client.post(
                    f"{base_url}/internal/notifications/outbox/dispatch",
                    params={"limit": 10},
                    headers=headers,
                )
                dispatched.raise_for_status()
    except Exception:
        logger.exception("Failed to send WhatsApp reply through notification-service")


def _verify_signature_if_required(body: bytes, supplied_signature: str) -> None:
    if os.getenv("WHATSAPP_SIGNATURE_REQUIRED", "").strip().lower() in {"0", "false", "no", "off"}:
        return

    app_env = os.getenv("APP_ENV", "development").strip().lower()
    if app_env in {"", "dev", "development", "local", "test"}:
        return

    secret = os.getenv("WHATSAPP_APP_SECRET", "").strip()
    if not secret:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="WhatsApp app secret is not configured",
        )

    expected = "sha256=" + hmac.new(secret.encode("utf-8"), body, hashlib.sha256).hexdigest()
    if not hmac.compare_digest(supplied_signature, expected):
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="invalid WhatsApp signature")


def _bool_from_env(name: str, default: bool) -> bool:
    raw = os.getenv(name)
    if raw is None or raw.strip() == "":
        return default
    return raw.strip().lower() in {"1", "true", "yes", "on"}


async def _extract_inbound_message(payload: dict[str, Any]) -> dict[str, Any] | None:
    for entry in payload.get("entry", []) or []:
        for change in entry.get("changes", []) or []:
            value = change.get("value", {}) or {}
            contact_name = _extract_contact_name(value)
            for message in value.get("messages", []) or []:
                sender = str(message.get("from") or "").strip()
                if not sender:
                    continue

                metadata: dict[str, Any] = {}
                if contact_name:
                    metadata["wa_name"] = contact_name

                message_type = str(message.get("type") or "").strip().lower()
                if message_type == "location" or message.get("location"):
                    return _extract_location_message(sender=sender, message=message, metadata=metadata)

                if message_type in {"audio", "voice"}:
                    return await _extract_audio_message(sender=sender, message=message, metadata=metadata)

                if message_type == "image":
                    return await _extract_image_message(sender=sender, message=message, metadata=metadata)

                text = str((message.get("text") or {}).get("body") or "").strip()
                if text:
                    return {"from": sender, "text": text, "metadata": metadata}
    return None


async def _extract_audio_message(
    *,
    sender: str,
    message: dict[str, Any],
    metadata: dict[str, Any],
) -> dict[str, Any]:
    media = message.get("audio") or message.get("voice") or {}
    media_id = str(media.get("id") or "").strip()
    if not media_id:
        return {"from": sender, "direct_reply": MEDIA_PROCESS_FAILURE_REPLY, "metadata": metadata}

    try:
        downloaded = await WhatsAppMediaClient.from_env().download(media_id)
        result = await MediaClient.from_env().process_audio(
            content_type=str(downloaded.get("content_type") or media.get("mime_type") or "audio/ogg"),
            size_bytes=int(downloaded.get("size_bytes") or 0),
            media_ref=f"whatsapp:{media_id}",
            content=downloaded["content"],
        )
    except (WhatsAppMediaDownloadError, MediaServiceError, RuntimeError):
        logger.exception("Failed to process WhatsApp audio media_id=%s", media_id)
        return {"from": sender, "direct_reply": MEDIA_PROCESS_FAILURE_REPLY, "metadata": metadata}

    transcript = str(result.get("transcript") or "").strip()
    if not result.get("success") or not transcript:
        return {"from": sender, "direct_reply": MEDIA_PROCESS_FAILURE_REPLY, "metadata": metadata}

    metadata.update(
        {
            "media_kind": "audio",
            "whatsapp_media_id": media_id,
            "media_job_id": result.get("job_id"),
            "media_provider_mode": result.get("provider_mode"),
        }
    )
    return {"from": sender, "text": transcript, "metadata": metadata}


async def _extract_image_message(
    *,
    sender: str,
    message: dict[str, Any],
    metadata: dict[str, Any],
) -> dict[str, Any]:
    media = message.get("image") or {}
    media_id = str(media.get("id") or "").strip()
    caption = str(media.get("caption") or "").strip()
    if not media_id:
        return {"from": sender, "direct_reply": MEDIA_PROCESS_FAILURE_REPLY, "metadata": metadata}

    result: dict[str, Any] = {}
    try:
        downloaded = await WhatsAppMediaClient.from_env().download(media_id)
        result = await MediaClient.from_env().process_image(
            content_type=str(downloaded.get("content_type") or media.get("mime_type") or "image/jpeg"),
            size_bytes=int(downloaded.get("size_bytes") or 0),
            media_ref=f"whatsapp:{media_id}",
            content=downloaded["content"],
        )
    except (WhatsAppMediaDownloadError, MediaServiceError, RuntimeError):
        logger.exception("Failed to process WhatsApp image media_id=%s", media_id)
        # Caption alone still lets the bot continue the conversation.
        if caption:
            metadata.update(
                {
                    "media_kind": "image",
                    "whatsapp_media_id": media_id,
                    "media_process_failed": True,
                }
            )
            return {"from": sender, "text": caption, "metadata": metadata}
        return {"from": sender, "direct_reply": MEDIA_PROCESS_FAILURE_REPLY, "metadata": metadata}

    extracted = str(result.get("extracted_text") or "").strip()
    if not result.get("success") or not extracted:
        if caption:
            metadata.update(
                {
                    "media_kind": "image",
                    "whatsapp_media_id": media_id,
                    "media_job_id": result.get("job_id"),
                    "media_provider_mode": result.get("provider_mode"),
                    "media_ocr_empty": True,
                }
            )
            return {"from": sender, "text": caption, "metadata": metadata}
        return {"from": sender, "direct_reply": MEDIA_PROCESS_FAILURE_REPLY, "metadata": metadata}

    text = f"{caption}\n{extracted}".strip() if caption else extracted
    metadata.update(
        {
            "media_kind": "image",
            "whatsapp_media_id": media_id,
            "media_job_id": result.get("job_id"),
            "media_provider_mode": result.get("provider_mode"),
        }
    )
    return {"from": sender, "text": text, "metadata": metadata}


def _extract_location_message(
    *,
    sender: str,
    message: dict[str, Any],
    metadata: dict[str, Any],
) -> dict[str, Any]:
    location = message.get("location") or {}
    try:
        lat = float(location.get("latitude"))
        lng = float(location.get("longitude"))
    except (TypeError, ValueError):
        return {
            "from": sender,
            "text": (
                "Recibi una ubicacion de WhatsApp, pero no pude leer sus coordenadas. "
                "Intenta enviar de nuevo tu ubicacion actual o dime la ciudad."
            ),
            "metadata": metadata,
        }

    location_name = _clean_metadata_text(location.get("name"), limit=200)
    location_address = _clean_metadata_text(location.get("address"), limit=500)

    if not is_colombia_latlng(lat, lng):
        return {
            "from": sender,
            "text": (
                "Recibi un pin de ubicacion, pero parece estar fuera de Colombia. "
                "Si estas en Colombia, intenta enviar de nuevo tu ubicacion actual; "
                "si no, dime la ciudad o barrio en Colombia."
            ),
            "metadata": metadata,
        }

    metadata.update(
        {
            "location_lat": lat,
            "location_lng": lng,
            "geo_lat": lat,
            "geo_lng": lng,
            "location_source": "whatsapp_location",
        }
    )
    if location_name:
        metadata["wa_location_name"] = location_name
    if location_address:
        metadata["wa_location_address"] = location_address

    parts = [
        "Acabo de compartir mi ubicacion actual por WhatsApp.",
        "Usa este pin GPS para buscar el centro mas cercano.",
    ]
    if location_name:
        parts.append(f"El pin figura como: {location_name}.")
    if location_address:
        parts.append(f"Direccion que muestra WhatsApp: {location_address}.")

    return {"from": sender, "text": " ".join(parts), "metadata": metadata}


def _extract_contact_name(value: dict[str, Any]) -> str | None:
    contacts = value.get("contacts") or []
    if not contacts:
        return None
    profile = (contacts[0] or {}).get("profile") or {}
    return _clean_metadata_text(profile.get("name"), limit=200)


def _clean_metadata_text(value: object, *, limit: int) -> str | None:
    text = str(value or "").strip()
    if not text:
        return None
    return text[:limit]
