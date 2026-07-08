from __future__ import annotations

from quote_service.shared.pricing import (
    QuoteError,
    generic_band,
    quote_course,
    quote_infraccion,
    quote_soat,
    quote_tecnomecanica,
)

from .schemas import CreateQuoteRequest, CreateQuoteResponse


async def create_quote(payload: CreateQuoteRequest) -> CreateQuoteResponse:
    service_type = _normalize_service_type(payload.service_type)
    quote = _quote_for_payload(service_type, payload)
    return CreateQuoteResponse(
        service_type=str(quote["service_type"]),
        price_min=int(quote["price_min"]),
        price_max=int(quote["price_max"]),
        price_cop=quote.get("price_cop") if isinstance(quote.get("price_cop"), int) else None,
        quote_type=str(quote.get("quote_type") or "range"),
        details=quote.get("details") if isinstance(quote.get("details"), dict) else {},
        message=quote.get("message") if isinstance(quote.get("message"), str) else None,
        options=quote.get("options") if isinstance(quote.get("options"), list) else [],
        disclaimer="Valor referencial sujeto a validacion final del proveedor o autoridad.",
    )


def _quote_for_payload(service_type: str, payload: CreateQuoteRequest) -> dict[str, object]:
    try:
        if service_type == "soat" and payload.vehicle_type and payload.cilindraje and payload.modelo:
            return quote_soat(
                vehicle_type=payload.vehicle_type,
                cilindraje=payload.cilindraje,
                modelo=payload.modelo,
                year=payload.year,
            )
        if service_type == "tecnomecanica" and (payload.categoria or payload.vehicle_type):
            return quote_tecnomecanica(category=payload.categoria or payload.vehicle_type or "")
        if service_type == "infraccion":
            return quote_infraccion(
                consulta=payload.consulta or "",
                codigo=payload.codigo,
                variable=payload.variable,
                year=payload.year,
            )
        if service_type == "curso_multa":
            return quote_course()
    except QuoteError as exc:
        return {
            "quote_type": "needs_clarification",
            "service_type": service_type,
            "price_min": 0,
            "price_max": 0,
            "message": str(exc),
        }
    return generic_band(service_type)


def _normalize_service_type(value: str) -> str:
    service_type = value.strip().lower().replace("-", "_")
    aliases = {
        "tecno": "tecnomecanica",
        "tecnomecanica": "tecnomecanica",
        "tecnomecanica": "tecnomecanica",
        "rtm": "tecnomecanica",
        "multa": "infraccion",
        "comparendo": "infraccion",
        "infracciones": "infraccion",
        "curso": "curso_multa",
        "cia": "curso_multa",
    }
    return aliases.get(service_type, service_type)
