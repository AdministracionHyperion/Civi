from __future__ import annotations

import os
import secrets
from typing import Annotated

from fastapi import Header, HTTPException, status


def _expected_basic() -> tuple[str, str] | None:
    user = os.getenv("ADMIN_USER", "").strip()
    password = os.getenv("ADMIN_PASSWORD", "").strip()
    if not user or not password:
        return None
    return user, password


async def require_admin_basic(
    x_admin_user: Annotated[str | None, Header(alias="X-Admin-User")] = None,
    x_admin_password: Annotated[str | None, Header(alias="X-Admin-Password")] = None,
) -> str:
    expected = _expected_basic()
    if expected is None:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="admin credentials are not configured",
        )
    expected_user, expected_password = expected
    if not (
        x_admin_user
        and x_admin_password
        and secrets.compare_digest(x_admin_user, expected_user)
        and secrets.compare_digest(x_admin_password, expected_password)
    ):
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="invalid admin credentials")
    return expected_user
