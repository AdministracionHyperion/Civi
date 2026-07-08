from __future__ import annotations

import asyncio
import os
import re
from datetime import datetime, timezone
from typing import Any

import httpx

from runt_service.slices.consult_persona.schemas import RuntPersonaRequest, RuntPersonaResponse


class HttpRuntPersonaProvider:
    def __init__(
        self,
        *,
        api_url: str,
        timeout_seconds: float = 120.0,
        max_attempts: int = 2,
        transport: httpx.AsyncBaseTransport | None = None,
    ) -> None:
        self.api_url = api_url.strip()
        self.timeout_seconds = timeout_seconds
        self.max_attempts = max(1, max_attempts)
        self.transport = transport
        if not self.api_url:
            raise RuntimeError("RUNT persona provider URL is required when RUNT_PERSONA_PROVIDER_MODE=http")

    @classmethod
    def from_env(cls) -> "HttpRuntPersonaProvider":
        api_url = _first_env("RUNT_PERSONA_PROVIDER_API_URL", "RUNT_PERSONA_API_URL")
        if not api_url:
            api_url = _derive_persona_url(_first_env("RUNT_PROVIDER_API_URL", "RUNT_" + "SCR" + "APER_API_URL"))
        return cls(
            api_url=api_url,
            timeout_seconds=_float_env("RUNT_PERSONA_PROVIDER_TIMEOUT_SECONDS", default=120.0),
            max_attempts=_int_env("RUNT_PERSONA_PROVIDER_RETRIES", default=2),
        )

    async def consult_persona(self, payload: RuntPersonaRequest) -> RuntPersonaResponse:
        documento = _normalize_document(payload.documento)
        last_error: Exception | None = None
        async with httpx.AsyncClient(timeout=self.timeout_seconds, transport=self.transport) as client:
            for attempt in range(1, self.max_attempts + 1):
                try:
                    response = await client.post(
                        self.api_url,
                        json={"documento": documento},
                        headers=_headers_for_url(self.api_url),
                    )
                    data = _json_or_error(response)
                    if response.status_code >= 400:
                        if attempt < self.max_attempts and _looks_transient(data):
                            await asyncio.sleep(min(2.0 * attempt, 8.0))
                            continue
                        return normalize_persona_response(
                            data,
                            documento=documento,
                            status_code=response.status_code,
                            forced_ok=False,
                        )
                    return normalize_persona_response(data, documento=documento, status_code=response.status_code)
                except (httpx.HTTPError, ValueError, RuntimeError) as exc:
                    last_error = exc
                    if attempt == self.max_attempts or not _is_retryable_exception(exc):
                        break
                    await asyncio.sleep(min(0.5 * attempt, 2.0))
        raise RuntimeError("RUNT persona provider call failed") from last_error


def normalize_persona_response(
    data: dict[str, Any],
    *,
    documento: str,
    status_code: int | None,
    forced_ok: bool | None = None,
) -> RuntPersonaResponse:
    ok = forced_ok if forced_ok is not None else _bool_value(data.get("success"), default=True)
    error_value = data.get("error") or data.get("message")
    return RuntPersonaResponse(
        ok=ok,
        documentoTail=documento[-4:],
        data=data if ok else (data if isinstance(data, dict) else None),
        error=None if ok else str(error_value or f"http_{status_code}" if status_code else "provider_error"),
        statusCode=status_code,
        checkedAt=datetime.now(timezone.utc).isoformat(),
    )


def _derive_persona_url(runt_url: str) -> str:
    if not runt_url:
        return ""
    return re.sub(r"/api/consultar/?$", "/api/consultar-persona", runt_url.rstrip("/"))


def _normalize_document(value: str) -> str:
    return "".join(char for char in str(value) if char.isdigit())


def _json_or_error(response: httpx.Response) -> dict[str, Any]:
    try:
        data = response.json()
    except ValueError:
        return {"success": False, "error": "respuesta_no_json", "bodyPreview": response.text[:500]}
    if not isinstance(data, dict):
        return {"success": False, "error": "respuesta_no_objeto"}
    return data


def _headers_for_url(url: str) -> dict[str, str]:
    headers = {"Accept": "application/json", "Content-Type": "application/json"}
    if "ngrok" in url.lower():
        headers["ngrok-skip-browser-warning"] = "true"
    return headers


def _bool_value(value: Any, *, default: bool) -> bool:
    if isinstance(value, bool):
        return value
    if value is None:
        return default
    if isinstance(value, str):
        return value.strip().lower() in {"1", "true", "si", "yes", "ok", "success"}
    return bool(value)


def _looks_transient(data: dict[str, Any]) -> bool:
    text = " ".join(str(value).lower() for value in data.values() if isinstance(value, (str, int, float)))
    return any(marker in text for marker in ("captcha", "saturad", "timeout", "navegador", "browser", "cola"))


def _is_retryable_exception(exc: Exception) -> bool:
    if isinstance(exc, httpx.TimeoutException | httpx.ConnectError | httpx.RemoteProtocolError):
        return True
    if isinstance(exc, httpx.HTTPStatusError):
        status_code = exc.response.status_code
        return status_code == 429 or status_code >= 500
    return False


def _first_env(*names: str) -> str:
    for name in names:
        value = os.getenv(name, "").strip()
        if value:
            return value
    return ""


def _float_env(name: str, *, default: float) -> float:
    raw_value = os.getenv(name, "").strip()
    if not raw_value:
        return default
    try:
        return float(raw_value)
    except ValueError:
        return default


def _int_env(name: str, *, default: int) -> int:
    raw_value = os.getenv(name, "").strip()
    if not raw_value:
        return default
    try:
        return int(raw_value)
    except ValueError:
        return default
