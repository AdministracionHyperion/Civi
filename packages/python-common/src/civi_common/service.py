from __future__ import annotations

import os
import secrets
from typing import Annotated

from fastapi import Header, HTTPException, status


def health_payload(service_name: str) -> dict[str, str]:
    return {
        "service": service_name,
        "status": "ok",
        "env": os.getenv("APP_ENV", "development"),
    }


async def require_internal_token(
    authorization: Annotated[str | None, Header(alias="Authorization")] = None,
) -> None:
    expected = os.getenv("INTERNAL_SERVICE_TOKEN", "").strip()
    if not expected:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="internal service token is not configured",
        )
    prefix = "Bearer "
    supplied = authorization[len(prefix):].strip() if authorization and authorization.startswith(prefix) else ""
    if not secrets.compare_digest(supplied, expected):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="invalid internal service token",
        )
