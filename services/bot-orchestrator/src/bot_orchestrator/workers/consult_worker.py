from __future__ import annotations

import asyncio
import logging
import os
from typing import Any

import httpx

from bot_orchestrator.adapters.outbound.notification_client import NotificationClient
from bot_orchestrator.adapters.outbound.quote_client import QuoteClient
from bot_orchestrator.adapters.outbound.vehicle_client import VehicleClient
from bot_orchestrator.shared.appointment_selection import shared_pending_store
from bot_orchestrator.shared.consult_jobs import (
    ConsultJob,
    ConsultJobRepository,
    get_consult_job_repository,
)
from bot_orchestrator.shared.vehicle_category import map_clase_to_quote_category
from bot_orchestrator.slices.run_turn.formatters import (
    format_multas_response,
    format_vigencia_response,
    tecno_needs_quote as _tecno_needs_quote,
)

logger = logging.getLogger("bot_orchestrator.workers.consult")


async def process_one_job(
    job: ConsultJob,
    *,
    repository: ConsultJobRepository | None = None,
    vehicle_client: VehicleClient | None = None,
    notification_client: NotificationClient | None = None,
    quote_client: QuoteClient | None = None,
) -> None:
    """Process a single consult job: call vehicle-service, quote if needed, save pending agenda, send via notification."""
    repo = repository or get_consult_job_repository()
    vc = vehicle_client or VehicleClient()
    nc = notification_client or NotificationClient()
    qc = quote_client or QuoteClient()

    try:
        if job.intent in ("soat", "tecnomecanica"):
            if not job.placa or not job.documento:
                raise RuntimeError("Faltan placa o documento para la consulta de vigencia")
            data = await vc.check_vigencia(
                placa=job.placa,
                documento=job.documento,
            )

            quote = await _maybe_quote_for_vigencia(intent=job.intent, data=data, quote_client=qc)
            formatted = format_vigencia_response(data, intent=job.intent, quote=quote)

            if job.intent == "tecnomecanica" and _tecno_needs_quote(data):
                shared_pending_store.save(
                    user_key=job.user_key,
                    channel=job.channel,
                    procedure="tecnomecanica",
                )

            repo.mark_done(job.job_id, {"data": data, "formatted": formatted, "quote": quote})
            await _send_and_dispatch(nc, to=job.user_key, channel=job.channel, body=formatted)
        elif job.intent == "multas":
            if not job.documento:
                raise RuntimeError("Falta documento para la consulta de multas")
            data = await vc.consult_multas(documento=job.documento, ciudad=job.ciudad)
            formatted = format_multas_response(data)
            repo.mark_done(job.job_id, {"data": data, "formatted": formatted})
            await _send_and_dispatch(nc, to=job.user_key, channel=job.channel, body=formatted)
        elif job.intent == "runt_profile":
            if not job.documento:
                raise RuntimeError("Falta documento para la consulta de perfil RUNT")
            from bot_orchestrator.slices.run_turn.formatters import format_runt_profile_response

            data = await vc.consult_runt_profile(documento=job.documento)
            formatted = format_runt_profile_response(data)
            repo.mark_done(job.job_id, {"data": data, "formatted": formatted})
            await _send_and_dispatch(nc, to=job.user_key, channel=job.channel, body=formatted)
        else:
            raise RuntimeError(f"Intento de consulta desconocido: {job.intent}")
    except Exception as exc:
        error_msg = str(exc)[:500]
        repo.mark_failed(job.job_id, error_msg)
        logger.exception("consult job %s failed", job.job_id)
        try:
            await _send_and_dispatch(
                nc,
                to=job.user_key,
                channel=job.channel,
                body=(
                    "Tuve un problema consultando la informacion. "
                    "Verifica los datos (placa y cedula) y lo intento de nuevo cuando quieras."
                ),
            )
        except Exception:
            logger.exception("failed to send failure notification for job %s", job.job_id)


async def _maybe_quote_for_vigencia(
    *,
    intent: str,
    data: dict[str, Any],
    quote_client: QuoteClient,
) -> dict[str, Any] | None:
    if intent == "tecnomecanica":
        if not _tecno_needs_quote(data):
            return None
        vehiculo = data.get("vehiculo") or {}
        categoria = map_clase_to_quote_category(vehiculo.get("claseVehiculo"))
        if categoria is None:
            return None
        try:
            return await quote_client.create(service_type="tecnomecanica", categoria=categoria)
        except (httpx.HTTPError, RuntimeError) as exc:
            logger.warning("quote tecnomecanica failed best-effort: %s", exc)
            return None

    if intent == "soat":
        from bot_orchestrator.slices.run_turn.formatters import soat_needs_quote as _soat_needs_quote

        if not _soat_needs_quote(data):
            return None
        vehiculo = data.get("vehiculo") or {}
        categoria = map_clase_to_quote_category(vehiculo.get("claseVehiculo"))
        if categoria not in {"moto", "carro", "campero", "camioneta", "taxi"}:
            return None
        cilindraje = _int_or_none(vehiculo.get("cilindraje"))
        modelo = _int_or_none(vehiculo.get("modelo"))
        if cilindraje is None or modelo is None:
            return None
        try:
            return await quote_client.create(
                service_type="soat",
                vehicle_type=categoria,
                cilindraje=cilindraje,
                modelo=modelo,
            )
        except (httpx.HTTPError, RuntimeError) as exc:
            logger.warning("quote soat failed best-effort: %s", exc)
            return None

    return None


def _int_or_none(value: object) -> int | None:
    if isinstance(value, bool):
        return None
    if isinstance(value, int):
        return value
    if isinstance(value, float) and value == int(value):
        return int(value)
    return None


async def _send_and_dispatch(
    nc: NotificationClient,
    *,
    to: str,
    channel: str,
    body: str,
) -> None:
    """Send message via notification-service and immediately dispatch outbox."""
    if channel.lower() != "whatsapp":
        logger.info("skip notification for channel=%s user_key=%s", channel, to)
        return
    normalized_to = "".join(char for char in to if char.isdigit() or char == "+")
    if not normalized_to:
        logger.warning("invalid user_key for notification: %s", to)
        return
    await nc.send_whatsapp_message(to=normalized_to, body=body)
    try:
        await nc.dispatch_outbox(limit=10)
    except Exception:
        logger.exception("dispatch_outbox failed for job, message may be delivered on next tick")


async def _notify_reaped_jobs(
    reaped: list[ConsultJob],
    *,
    notification_client: NotificationClient | None = None,
) -> None:
    """Tell each user whose job got reaped that the consult could not be completed."""
    nc = notification_client or NotificationClient()
    for job in reaped:
        try:
            await _send_and_dispatch(
                nc,
                to=job.user_key,
                channel=job.channel,
                body=(
                    "Tu consulta tardo mas de lo esperado y no pude completarla. "
                    "Verifica los datos (placa y cedula) e intentalo de nuevo cuando quieras."
                ),
            )
        except Exception:
            logger.exception("failed to notify reaped job %s", job.job_id)


async def run_once(
    *,
    repository: ConsultJobRepository | None = None,
    vehicle_client: VehicleClient | None = None,
    notification_client: NotificationClient | None = None,
    quote_client: QuoteClient | None = None,
    max_concurrent: int | None = None,
) -> int:
    """Process pending jobs (up to max_concurrent in parallel). Returns number of jobs processed."""
    repo = repository or get_consult_job_repository()
    if max_concurrent is None:
        max_concurrent = _int_from_env("BOT_CONSULT_MAX_CONCURRENT", 3)

    # Dequeue up to max_concurrent jobs
    jobs: list[ConsultJob] = []
    for _ in range(max_concurrent):
        job = repo.dequeue_next_pending()
        if job is None:
            break
        jobs.append(job)

    if not jobs:
        return 0

    tasks = [
        process_one_job(
            job,
            repository=repo,
            vehicle_client=vehicle_client,
            notification_client=notification_client,
            quote_client=quote_client,
        )
        for job in jobs
    ]
    await asyncio.gather(*tasks)
    return len(jobs)


async def run_forever(
    *,
    interval_seconds: float | None = None,
    max_concurrent: int | None = None,
) -> None:
    interval = interval_seconds
    if interval is None:
        interval = _float_from_env("BOT_CONSULT_WORKER_INTERVAL_SECONDS", 5.0)

    reaper_interval = _float_from_env("BOT_CONSULT_REAPER_INTERVAL_SECONDS", 30.0)
    reaper_timeout = _int_from_env("BOT_CONSULT_REAPER_TIMEOUT_SECONDS", 300)
    last_reap = 0.0
    tick = 0

    while True:
        try:
            # Reap stuck jobs periodically
            tick += 1
            if reaper_timeout > 0 and tick * interval >= last_reap + reaper_interval:
                repo = get_consult_job_repository()
                try:
                    reaped = repo.reap_stuck_jobs(max_processing_seconds=reaper_timeout)
                    if reaped:
                        logger.warning("reaped %d stuck consult jobs", len(reaped))
                        await _notify_reaped_jobs(reaped)
                except Exception:
                    logger.exception("reaper tick failed")
                last_reap += reaper_interval

            processed = await run_once(
                max_concurrent=max_concurrent,
            )
            if processed:
                logger.info("consult worker processed %d job(s)", processed)
        except Exception:
            logger.exception("consult worker tick failed")
        await asyncio.sleep(interval)


def main() -> None:
    logging.basicConfig(level=os.getenv("LOG_LEVEL", "INFO"))
    asyncio.run(run_forever())


def _float_from_env(name: str, default: float) -> float:
    raw = os.getenv(name, "").strip()
    try:
        value = float(raw)
    except ValueError:
        return default
    return value if value > 0 else default


def _int_from_env(name: str, default: int) -> int:
    raw = os.getenv(name, "").strip()
    try:
        value = int(raw)
    except ValueError:
        return default
    return value if value >= 0 else default


if __name__ == "__main__":
    main()
