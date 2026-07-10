from __future__ import annotations

from admin_service.adapters.outbound.places_summary_client import PlacesSummaryClient
from admin_service.adapters.outbound.service_status_client import (
    DEFAULT_SERVICE_URLS,
    InternalServiceStatusClient,
    StatusClient,
)

from .schemas import DashboardSummaryResponse


async def dashboard_summary(*, status_client: StatusClient | None = None) -> DashboardSummaryResponse:
    services = list(DEFAULT_SERVICE_URLS.keys())
    try:
        service_statuses = await (status_client or InternalServiceStatusClient()).fetch_statuses()
    except RuntimeError as exc:
        service_statuses = [
            {
                "service": service,
                "status": "degraded",
                "error": str(exc),
            }
            for service in services
        ]

    places_catalog = None
    try:
        places_catalog = await PlacesSummaryClient().catalog_summary()
    except Exception as exc:  # noqa: BLE001
        places_catalog = {"success": False, "error": str(exc)}

    return DashboardSummaryResponse(
        services=services,
        service_statuses=service_statuses,
        appointments_visible=False,
        places_catalog=places_catalog,
    )
