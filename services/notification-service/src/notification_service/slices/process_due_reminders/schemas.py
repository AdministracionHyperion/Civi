from __future__ import annotations

from pydantic import BaseModel


class ProcessDueRemindersResponse(BaseModel):
    processed: list[dict[str, object]]
    count: int
