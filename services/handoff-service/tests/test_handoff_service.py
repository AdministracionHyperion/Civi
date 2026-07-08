from __future__ import annotations

import pytest
from httpx import ASGITransport, AsyncClient

from handoff_service.main import app


@pytest.mark.asyncio
async def test_handoff_service_queues_case(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("INTERNAL_SERVICE_TOKEN", "test-token")
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        response = await client.post(
            "/internal/handoffs",
            headers={"Authorization": "Bearer test-token"},
            json={"user_key": "u1", "reason": "necesita asesor"},
        )
    assert response.status_code == 200
    assert response.json()["status"] == "queued"
