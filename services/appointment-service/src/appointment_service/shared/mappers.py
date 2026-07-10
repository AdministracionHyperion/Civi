from __future__ import annotations

from appointment_service.shared.repository import AppointmentRecord


def appointment_to_dict(record: AppointmentRecord) -> dict[str, object]:
    return {
        "id": record.id,
        "user_key": record.user_key,
        "procedure": record.procedure,
        "place": {
            "id": record.place_id,
            "name": record.place_name,
            "address": record.place_address,
            "city": record.place_city,
        },
        "starts_at": record.starts_at,
        "status": record.status,
        "created_at": record.created_at,
        "partner_notified_at": record.partner_notified_at,
        "partner_confirmed_at": record.partner_confirmed_at,
        "client_notification_to": record.client_notification_to,
        "partner_notification_to": record.partner_notification_to,
    }
