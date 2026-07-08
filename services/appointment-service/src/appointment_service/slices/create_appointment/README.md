# create_appointment slice

Owner for appointment creation rules. The slice exposes an internal HTTP contract, persists the appointment through the appointment repository and optionally schedules a notification through `notification-service`.
