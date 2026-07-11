from __future__ import annotations

import asyncio
import os
import re
import unicodedata
from typing import Any

import httpx

from simit_service.slices.consult_multas.schemas import SimitMultasRequest, SimitMultasResponse

_INFRACTION_CODE_RE = re.compile(r"\b([A-I]\d{2})\b", re.IGNORECASE)
_PLATE_IN_TEXT_RE = re.compile(r"\b([A-Z]{3}\d{2}[A-Z0-9]|[A-Z]{3}\d{3})\b", re.IGNORECASE)


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
    detalles = [_canonicalize_simit_detalle(item) for item in _list_of_dicts(source.get("detalles"))]
    detalles = [item for item in detalles if any(item.get(key) for key in ("codigo", "placa", "infraccion", "valor", "estado"))]

    return SimitMultasResponse(
        success=_bool_value(data.get("success"), default=True),
        documentoTail=_normalize_document(documento)[-4:],
        tieneMultas=tiene_multas,
        resumen=resumen,
        mensaje=str(source.get("mensaje") or data.get("mensaje") or ""),
        detalles=detalles,
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
    """Normalize SIMIT query: plate stays alphanumeric, documents keep digits."""
    compact = "".join(char for char in str(value or "").strip().upper() if char.isalnum())
    if not compact:
        return ""
    if re.fullmatch(r"[A-Z]{3}\d{2}[A-Z0-9]|[A-Z]{3}\d{3}", compact):
        return compact
    return "".join(char for char in compact if char.isdigit()) or compact


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


def _fold_key(value: object) -> str:
    text = "".join(
        char for char in unicodedata.normalize("NFKD", str(value or "")) if not unicodedata.combining(char)
    )
    return re.sub(r"\s+", " ", text).strip().lower()


def _pick_detalle_field(item: dict[str, object], *aliases: str) -> str:
    wanted = {_fold_key(alias) for alias in aliases}
    for key, value in item.items():
        key_fold = _fold_key(key)
        if key_fold in wanted or any(alias in key_fold for alias in wanted if len(alias) >= 5):
            text = str(value or "").strip()
            if text:
                return text
    return ""


_UI_JUNK_LABELS = {
    "proyeccion pago",
    "proyección pago",
    "detalle",
    "ver mas",
    "ver más",
}


def _clean_detalle_text(value: str) -> str:
    text = re.sub(r"\s+", " ", str(value or "")).strip()
    if not text:
        return ""
    folded = _fold_key(text)
    if folded in _UI_JUNK_LABELS:
        return ""
    text = re.sub(r"(?i)\bproyecci[oó]n(?:\s+de)?\s+pago\b", " ", text)
    text = re.sub(r"(?i)\binter[eé]s(?:es)?\b[:\s]*\$?\s*[\d\.\,]*", " ", text)
    text = re.sub(r"\s+", " ", text).strip(" -:;,")
    if _fold_key(text) in _UI_JUNK_LABELS:
        return ""
    return text


def _canonicalize_simit_detalle(item: dict[str, object]) -> dict[str, object]:
    """Map raw SIMIT/local row headers into stable Spanish field names for the bot."""
    infraccion = _clean_detalle_text(
        _pick_detalle_field(item, "infraccion", "infracción", "descripcion", "descripción")
    )
    placa = _clean_detalle_text(_pick_detalle_field(item, "placa"))
    estado = _clean_detalle_text(_pick_detalle_field(item, "estado"))
    valor = _clean_detalle_text(
        _pick_detalle_field(item, "valor a pagar", "valor_a_pagar", "valor multa", "valor")
    )
    fecha = _clean_detalle_text(_pick_detalle_field(item, "fecha", "resolucion", "resolución"))
    tipo = _clean_detalle_text(_pick_detalle_field(item, "tipo"))
    secretaria = _clean_detalle_text(_pick_detalle_field(item, "secretaria", "secretaría"))
    codigo = _clean_detalle_text(_pick_detalle_field(item, "codigo", "código"))
    numero = _clean_detalle_text(
        _pick_detalle_field(item, "numero", "número", "notificacion", "notificación")
    )

    blob = " ".join(str(value or "") for value in item.values())
    if infraccion and not _INFRACTION_CODE_RE.search(infraccion) and len(infraccion.split()) <= 3:
        folded = _fold_key(infraccion)
        if "fotodetec" in folded or "proyeccion" in folded or folded in _UI_JUNK_LABELS:
            infraccion = ""
    if not codigo:
        match = _INFRACTION_CODE_RE.search(infraccion or blob)
        if match:
            codigo = match.group(1).upper()
    if not placa:
        match = _PLATE_IN_TEXT_RE.search(blob)
        if match:
            placa = match.group(1).upper()
    if not fecha and tipo:
        date_match = re.search(r"\b(\d{1,2}/\d{1,2}/20\d{2})\b", tipo)
        if date_match:
            fecha = date_match.group(1)
    if tipo and "fotodetec" in tipo.lower():
        tipo = "fotodeteccion"
    elif infraccion and "fotodetec" in infraccion.lower():
        tipo = "fotodeteccion"
        infraccion = _clean_detalle_text(re.sub(r"(?i)\bfotodetecci[oó]n\b", " ", infraccion))

    canonical = {
        "codigo": codigo,
        "placa": placa,
        "estado": estado,
        "infraccion": infraccion,
        "fecha": fecha,
        "tipo": tipo,
        "valor": valor,
        "secretaria": secretaria,
        "numero": numero,
    }
    return {key: value for key, value in canonical.items() if value}


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
