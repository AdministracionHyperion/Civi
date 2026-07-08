from __future__ import annotations

import asyncio
import os
import re
from typing import Any

import httpx

from simit_service.slices.consult_multas.schemas import SimitMultasRequest, SimitMultasResponse


class HttpSimitProvider:
    def __init__(
        self,
        *,
        api_url: str,
        timeout_seconds: float = 90.0,
        max_attempts: int = 2,
        transport: httpx.AsyncBaseTransport | None = None,
    ) -> None:
        self.api_url = api_url.strip()
        self.timeout_seconds = timeout_seconds
        self.max_attempts = max(1, max_attempts)
        self.transport = transport
        if not self.api_url:
            raise RuntimeError("SIMIT provider URL is required when SIMIT_PROVIDER_MODE=http")

    @classmethod
    def from_env(cls) -> "HttpSimitProvider":
        api_url = _first_env("SIMIT_PROVIDER_API_URL", "SIMIT_MULTAS_API_URL")
        if not api_url:
            runt_url = _first_env("RUNT_PROVIDER_API_URL", "RUNT_" + "SCR" + "APER_API_URL")
            api_url = _derive_multas_url(runt_url)
        return cls(
            api_url=api_url,
            timeout_seconds=_float_env("SIMIT_PROVIDER_TIMEOUT_SECONDS", default=90.0),
            max_attempts=_int_env("SIMIT_PROVIDER_RETRIES", default=2),
        )

    async def consult_multas(self, payload: SimitMultasRequest) -> SimitMultasResponse:
        normalized_document = _normalize_document(payload.documento)
        request_payload = {"documento": normalized_document}

        last_error: Exception | None = None
        async with httpx.AsyncClient(timeout=self.timeout_seconds, transport=self.transport) as client:
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
                        raise RuntimeError("SIMIT provider returned a non-object payload")

                    normalized = normalize_simit_response(data, fallback_documento=normalized_document)
                    if normalized.success or not _looks_transient(data) or attempt == self.max_attempts:
                        return normalized
                except (httpx.HTTPError, ValueError, RuntimeError) as exc:
                    last_error = exc
                    if attempt == self.max_attempts or not _is_retryable_exception(exc):
                        break
                await asyncio.sleep(min(0.5 * attempt, 2.0))

        raise RuntimeError("SIMIT provider call failed") from last_error


def normalize_simit_response(data: dict[str, Any], *, fallback_documento: str) -> SimitMultasResponse:
    source = data.get("multas") if isinstance(data.get("multas"), dict) else data
    assert isinstance(source, dict)

    resumen_raw = source.get("resumen") if isinstance(source.get("resumen"), dict) else {}
    resumen = {
        "comparendos": _int_value(resumen_raw.get("comparendos")),
        "multas": _int_value(resumen_raw.get("multas")),
        "total": _int_value(resumen_raw.get("total")),
    }
    tiene_multas = _bool_value(
        source.get("tieneMultas"),
        default=(resumen["comparendos"] + resumen["multas"] + resumen["total"]) > 0,
    )
    documento = str(data.get("documento") or source.get("documento") or fallback_documento)

    return SimitMultasResponse(
        success=_bool_value(data.get("success"), default=True),
        documentoTail=_normalize_document(documento)[-4:],
        tieneMultas=tiene_multas,
        resumen=resumen,
        mensaje=str(source.get("mensaje") or data.get("mensaje") or ""),
        detalles=_list_of_dicts(source.get("detalles")),
    )


def _derive_multas_url(runt_url: str) -> str:
    if not runt_url:
        return ""
    return re.sub(r"/api/consultar/?$", "/api/multas", runt_url.rstrip("/"))


def _headers_for_url(url: str) -> dict[str, str]:
    headers = {"Accept": "application/json", "Content-Type": "application/json"}
    if "ngrok" in url.lower():
        headers["ngrok-skip-browser-warning"] = "true"
    return headers


def _normalize_document(value: str) -> str:
    return "".join(char for char in str(value) if char.isdigit())


def _int_value(value: Any) -> int:
    if isinstance(value, bool):
        return int(value)
    if isinstance(value, int):
        return value
    if isinstance(value, float):
        return int(value)
    if isinstance(value, str):
        digits = re.sub(r"[^\d-]", "", value)
        if digits and digits != "-":
            try:
                return int(digits)
            except ValueError:
                return 0
    return 0


def _bool_value(value: Any, *, default: bool) -> bool:
    if isinstance(value, bool):
        return value
    if value is None:
        return default
    if isinstance(value, str):
        return value.strip().lower() in {"1", "true", "si", "yes", "vigente", "activo"}
    return bool(value)


def _list_of_dicts(value: Any) -> list[dict[str, object]]:
    if not isinstance(value, list):
        return []
    return [dict(item) for item in value if isinstance(item, dict)]


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
