from __future__ import annotations

import asyncio
from dataclasses import dataclass
import logging
import os

from notification_service.slices.dispatch_outbox.schemas import DispatchOutboxResponse
from notification_service.slices.dispatch_outbox.use_case import dispatch_outbox
from notification_service.slices.process_due_reminders.use_case import process_due_reminders

logger = logging.getLogger("notification_service.workers.reminders")


@dataclass(frozen=True)
class WorkerTickResult:
    due_processed: int
    outbox_dispatched: int


async def run_once(
    *,
    now: str | None = None,
    limit: int | None = None,
    dispatch_outbox_enabled: bool | None = None,
) -> WorkerTickResult:
    active_limit = limit if limit is not None else _int_from_env("NOTIFICATION_WORKER_LIMIT", 50)
    should_dispatch = (
        dispatch_outbox_enabled
        if dispatch_outbox_enabled is not None
        else _bool_from_env("NOTIFICATION_WORKER_DISPATCH_OUTBOX", False)
    )
    due_result = await process_due_reminders(now=now, limit=active_limit)
    dispatch_result: DispatchOutboxResponse | None = None
    if should_dispatch:
        dispatch_result = await dispatch_outbox(limit=active_limit)

    return WorkerTickResult(
        due_processed=due_result.count,
        outbox_dispatched=len(dispatch_result.dispatched) if dispatch_result else 0,
    )


async def run_forever(*, interval_seconds: float | None = None) -> None:
    interval = interval_seconds
    if interval is None:
        interval = _float_from_env("NOTIFICATION_WORKER_INTERVAL_SECONDS", 30.0)
    while True:
        try:
            result = await run_once()
            logger.info(
                "notification worker tick completed due_processed=%s outbox_dispatched=%s",
                result.due_processed,
                result.outbox_dispatched,
            )
        except Exception:
            logger.exception("notification worker tick failed")
        await asyncio.sleep(interval)


def main() -> None:
    logging.basicConfig(level=os.getenv("LOG_LEVEL", "INFO"))
    asyncio.run(run_forever())


def _bool_from_env(name: str, default: bool) -> bool:
    raw = os.getenv(name)
    if raw is None or raw.strip() == "":
        return default
    return raw.strip().lower() in {"1", "true", "yes", "on"}


def _int_from_env(name: str, default: int) -> int:
    raw = os.getenv(name, "").strip()
    try:
        value = int(raw)
    except ValueError:
        return default
    return value if value > 0 else default


def _float_from_env(name: str, default: float) -> float:
    raw = os.getenv(name, "").strip()
    try:
        value = float(raw)
    except ValueError:
        return default
    return value if value > 0 else default


if __name__ == "__main__":
    main()
