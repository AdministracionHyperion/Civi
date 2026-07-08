from __future__ import annotations

from pydantic import BaseModel


class AuthenticateAdminResponse(BaseModel):
    success: bool = True
    role: str = "admin"
