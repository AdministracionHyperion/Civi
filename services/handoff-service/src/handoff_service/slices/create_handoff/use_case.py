from __future__ import annotations

import hashlib

from .schemas import CreateHandoffRequest, CreateHandoffResponse


async def create_handoff(payload: CreateHandoffRequest) -> CreateHandoffResponse:
    digest = hashlib.sha256(f"{payload.user_key}:{payload.reason}".encode()).hexdigest()[:16]
    return CreateHandoffResponse(
        handoff_id=f"handoff_{digest}",
        status="queued",
        message="Te paso con un asesor. Ya deje el caso en cola con el contexto necesario.",
    )
