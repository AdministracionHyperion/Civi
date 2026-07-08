from __future__ import annotations

import asyncio
import os
from typing import Any

import httpx

from runt_service.slices.check_vigencia.schemas import RuntVigenciaRequest, RuntVigenciaResponse


class HttpRuntProvider:
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
            raise RuntimeError("RUNT provider URL is required when RUNT_PROVIDER_MODE=http")

    @classmethod
    def from_env(cls) -> "HttpRuntProvider":
        api_url = _first_env("RUNT_PROVIDER_API_URL", "RUNT_" + "SCR" + "APER_API_URL")
        return cls(
            api_url=api_url,
            timeout_seconds=_float_env("RUNT_PROVIDER_TIMEOUT_SECONDS", default=120.0),
            max_attempts=_int_env("RUNT_PROVIDER_RETRIES", default=2),
        )

    async def check_vigencia(self, payload: RuntVigenciaRequest) -> RuntVigenciaResponse:
        request_payload = {
            "placa": payload.placa.strip().upper(),
            "documento": payload.documento.strip(),
            "tipoDocumento": payload.tipo_documento.strip().upper(),
            "forzarActualizacion": payload.forzar_actualizacion,
        }

        last_error: Exception | None = None
        async with httpx.AsyncClient(
            timeout=self.timeout_seconds,
            transport=self.transport,
        ) as client:
            for attempt in range(1, self.max_attempts + 1):
                try:
                    response = await client.post(
                        self.api_url,
                        json=request_payload,
                        headers=_headers_for_url(self.api_url),
                    )
                    response.raise_for_status()
                    data = response.json()
                    if not isinstance(data, dict):
                        raise RuntimeError("RUNT provider returned a non-object payload")

                    normalized = normalize_runt_response(data, fallback_placa=request_payload["placa"])
                    if normalized.success or not _looks_transient(data) or attempt == self.max_attempts:
                        return normalized
                except (httpx.HTTPError, ValueError, RuntimeError) as exc:
                    last_error = exc
                    if attempt == self.max_attempts or not _is_retryable_exception(exc):
                        break
                await asyncio.sleep(min(0.5 * attempt, 2.0))

        raise RuntimeError("RUNT provider call failed") from last_error


def normalize_runt_response(data: dict[str, Any], *, fallback_placa: str) -> RuntVigenciaResponse:
    vehiculo = _dict_or_empty(data.get("vehiculo") or data.get("infoGeneral"))
    soat = _dict_or_empty(data.get("soat") or data.get("soatData"))
    rtm = _dict_or_empty(data.get("rtm") or data.get("rtmData"))

    placa = str(data.get("placa") or vehiculo.get("placa") or fallback_placa).strip().upper()
    if "placa" not in vehiculo:
        vehiculo = {"placa": placa, **vehiculo}

    multas = data.get("multas")
    return RuntVigenciaResponse(
        success=_bool_value(data.get("success"), default=True),
        placa=placa,
        vehiculo=vehiculo,
        soat=soat,
        rtm=rtm,
        multas=multas if isinstance(multas, dict) else None,
        alertas=_list_of_dicts(data.get("alertas")),
        fromCache=_bool_value(data.get("fromCache"), default=False),
    )


def _headers_for_url(url: str) -> dict[str, str]:
    headers = {"Accept": "application/json", "Content-Type": "application/json"}
    if "ngrok" in url.lower():
        headers["ngrok-skip-browser-warning"] = "true"
    return headers


def _dict_or_empty(value: Any) -> dict[str, Any]:
    return dict(value) if isinstance(value, dict) else {}


def _list_of_dicts(value: Any) -> list[dict[str, Any]]:
    if not isinstance(value, list):
        return []
    return [dict(item) for item in value if isinstance(item, dict)]


def _bool_value(value: Any, *, default: bool) -> bool:
    if isinstance(value, bool):
        return value
    if value is None:
        return default
    if isinstance(value, str):
        return value.strip().lower() in {"1", "true", "si", "yes", "vigente"}
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
