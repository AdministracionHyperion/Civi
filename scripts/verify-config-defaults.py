from __future__ import annotations

from pathlib import Path
from typing import Any

import yaml


ROOT = Path(__file__).resolve().parents[1]

REQUIRED_ENV_DEFAULTS = {
    "EVENT_PUBLISHER_MODE": "disabled",
    "LLM_PROVIDER_MODE": "disabled",
    "WHATSAPP_PROVIDER_MODE": "disabled",
    "MEDIA_AUDIO_PROVIDER_MODE": "disabled",
    "MEDIA_IMAGE_PROVIDER_MODE": "disabled",
    "RUNT_PROVIDER_MODE": "local",
    "RUNT_PERSONA_PROVIDER_MODE": "local",
    "SIMIT_PROVIDER_MODE": "local",
    "NOTIFICATION_WORKER_DISPATCH_OUTBOX": "false",
    "CHANNEL_PUBLIC_RATE_LIMIT_ENABLED": "true",
    "CHANNEL_CORS_ALLOWED_ORIGINS": "",
}

EMPTY_ENV_CREDENTIALS = {
    "WHATSAPP_VERIFY_TOKEN",
    "WHATSAPP_APP_SECRET",
    "OPENAI_API_KEY",
    "OPENAI_LLM_MODEL",
    "DEEPSEEK_API_KEY",
    "GROQ_API_KEY",
    "WHATSAPP_ACCESS_TOKEN",
    "WHATSAPP_PHONE_NUMBER_ID",
    "OPENAI_AUDIO_TRANSCRIPTION_MODEL",
    "OPENAI_IMAGE_VISION_MODEL",
    "RUNT_PROVIDER_API_URL",
    "RUNT_PERSONA_PROVIDER_API_URL",
    "SIMIT_PROVIDER_API_URL",
    "CAPTCHA_API_KEY",
    "ADMIN_USER",
    "ADMIN_PASSWORD",
}

COMPOSE_REQUIRED_DEFAULTS = {
    "bot-orchestrator": {
        "LLM_PROVIDER_MODE": "${llm_provider_mode:-disabled}",
    },
    "notification-service": {
        "WHATSAPP_PROVIDER_MODE": "${whatsapp_provider_mode:-disabled}",
    },
    "notification-worker": {
        "WHATSAPP_PROVIDER_MODE": "${whatsapp_provider_mode:-disabled}",
        "NOTIFICATION_WORKER_DISPATCH_OUTBOX": "false",
    },
    "media-service": {
        "MEDIA_AUDIO_PROVIDER_MODE": "${media_audio_provider_mode:-disabled}",
        "MEDIA_IMAGE_PROVIDER_MODE": "${media_image_provider_mode:-disabled}",
    },
    "runt-service": {
        "RUNT_PROVIDER_MODE": "${runt_provider_mode:-local}",
        "RUNT_PERSONA_PROVIDER_MODE": "${runt_persona_provider_mode:-local}",
    },
    "simit-service": {
        "SIMIT_PROVIDER_MODE": "${simit_provider_mode:-local}",
    },
}

COMPOSE_EVENT_PRODUCERS = {
    "channel-gateway",
    "conversation-service",
    "appointment-service",
    "notification-service",
    "notification-worker",
}

WORKERS_WITHOUT_PORTS = {
    "notification-worker",
    "admin-event-audit-worker",
}


def main() -> None:
    failures: list[str] = []
    env_values = _read_env_example()
    failures.extend(_verify_env_example(env_values))
    compose = _read_compose()
    failures.extend(_verify_compose(compose))

    if failures:
        for failure in failures:
            print(failure)
        raise SystemExit("Configuration default verification failed.")

    print("Civi configuration defaults verification passed.")


def _read_env_example() -> dict[str, str]:
    values: dict[str, str] = {}
    for raw_line in (ROOT / ".env.example").read_text(encoding="utf-8").splitlines():
        line = raw_line.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue
        key, value = line.split("=", 1)
        values[key.strip()] = value.strip()
    return values


def _verify_env_example(env_values: dict[str, str]) -> list[str]:
    failures: list[str] = []
    for key, expected_value in REQUIRED_ENV_DEFAULTS.items():
        actual = env_values.get(key)
        if actual != expected_value:
            failures.append(f".env.example {key} must default to {expected_value!r}, got {actual!r}")
    for key in EMPTY_ENV_CREDENTIALS:
        actual = env_values.get(key)
        if actual is None:
            failures.append(f".env.example must declare credential placeholder {key}")
        elif actual != "":
            failures.append(f".env.example credential placeholder {key} must be empty")
    return failures


def _read_compose() -> dict[str, Any]:
    return yaml.safe_load((ROOT / "infra" / "docker-compose.local.yml").read_text(encoding="utf-8"))


def _verify_compose(compose: dict[str, Any]) -> list[str]:
    failures: list[str] = []
    services = compose.get("services") or {}
    for service_name in WORKERS_WITHOUT_PORTS:
        service = services.get(service_name) or {}
        if "ports" in service:
            failures.append(f"{service_name} must not expose public ports in compose")

    for service_name, required in COMPOSE_REQUIRED_DEFAULTS.items():
        environment = _environment_for(services, service_name)
        for key, expected_value in required.items():
            actual = str(environment.get(key, "")).strip().lower()
            if actual != expected_value:
                failures.append(f"{service_name} {key} must default to {expected_value!r}, got {environment.get(key)!r}")

    for service_name in COMPOSE_EVENT_PRODUCERS:
        environment = _environment_for(services, service_name)
        actual = str(environment.get("EVENT_PUBLISHER_MODE", "")).strip()
        if actual != "${EVENT_PUBLISHER_MODE:-disabled}":
            failures.append(
                f"{service_name} EVENT_PUBLISHER_MODE must default through ${{EVENT_PUBLISHER_MODE:-disabled}}"
            )

    admin_event_worker_env = _environment_for(services, "admin-event-audit-worker")
    if "EVENT_REDIS_URL" not in admin_event_worker_env:
        failures.append("admin-event-audit-worker must declare EVENT_REDIS_URL")
    if "EVENT_CHANNEL_PREFIX" not in admin_event_worker_env:
        failures.append("admin-event-audit-worker must declare EVENT_CHANNEL_PREFIX")

    retired_service = "sc" + "raper-service"
    if retired_service in services:
        failures.append("retired Node RUNT/SIMIT service must not exist in the clean product compose")
    for required_service in [
        "runt-service",
        "simit-service",
        "knowledge-service",
        "quote-service",
        "billing-service",
        "handoff-service",
    ]:
        if required_service not in services:
            failures.append(f"{required_service} must exist in the clean product compose")

    return failures


def _environment_for(services: dict[str, Any], service_name: str) -> dict[str, Any]:
    service = services.get(service_name)
    if not isinstance(service, dict):
        raise SystemExit(f"Missing compose service: {service_name}")
    environment = service.get("environment") or {}
    if isinstance(environment, list):
        parsed: dict[str, Any] = {}
        for item in environment:
            key, _, value = str(item).partition("=")
            parsed[key] = value
        return parsed
    return dict(environment)


if __name__ == "__main__":
    main()
