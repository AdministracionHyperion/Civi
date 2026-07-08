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
    }
