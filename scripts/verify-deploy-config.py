from __future__ import annotations

import argparse
from pathlib import Path


PLACEHOLDER_MARKERS = (
    "__replace",
    "change-me",
    "local-only",
    "<",
    "your_",
    "example.com",
)


BASE_REQUIRED = {
    "APP_ENV",
    "LOG_LEVEL",
    "PUBLIC_BASE_URL",
    "INTERNAL_SERVICE_TOKEN",
    "POSTGRES_USER",
    "POSTGRES_PASSWORD",
    "POSTGRES_DB",
    "DATABASE_URL",
    "REDIS_PASSWORD",
    "EVENT_PUBLISHER_MODE",
    "EVENT_REDIS_URL",
    "EVENT_CHANNEL_PREFIX",
    "CHANNEL_GATEWAY_PORT",
    "CHANNEL_BIND",
    "CHANNEL_PUBLIC_RATE_LIMIT_ENABLED",
    "WHATSAPP_PROVIDER_MODE",
    "WHATSAPP_GRAPH_API_VERSION",
    "WHATSAPP_ACCESS_TOKEN",
    "WHATSAPP_PHONE_NUMBER_ID",
    "WHATSAPP_VERIFY_TOKEN",
    "WHATSAPP_SIGNATURE_REQUIRED",
    "LLM_PROVIDER_MODE",
    "MEDIA_AUDIO_PROVIDER_MODE",
    "MEDIA_IMAGE_PROVIDER_MODE",
    "RUNT_PROVIDER_MODE",
    "RUNT_PERSONA_PROVIDER_MODE",
    "SIMIT_PROVIDER_MODE",
    "ADMIN_USER",
    "ADMIN_PASSWORD",
}

SQL_REQUIRED = {
    "CONVERSATION_REPOSITORY_MODE",
    "CONVERSATION_AUTO_CREATE_SCHEMA",
    "VEHICLE_CACHE_MODE",
    "VEHICLE_AUTO_CREATE_SCHEMA",
    "PLACES_REPOSITORY_MODE",
    "PLACES_AUTO_CREATE_SCHEMA",
    "APPOINTMENT_REPOSITORY_MODE",
    "APPOINTMENT_AUTO_CREATE_SCHEMA",
    "NOTIFICATION_REPOSITORY_MODE",
    "NOTIFICATION_AUTO_CREATE_SCHEMA",
    "MEDIA_REPOSITORY_MODE",
    "MEDIA_AUTO_CREATE_SCHEMA",
    "ADMIN_AUDIT_REPOSITORY_MODE",
    "ADMIN_AUTO_CREATE_SCHEMA",
}


def parse_env(path: Path) -> dict[str, str]:
    env: dict[str, str] = {}
    for line_number, raw_line in enumerate(path.read_text(encoding="utf-8").splitlines(), start=1):
        line = raw_line.strip()
        if not line or line.startswith("#"):
            continue
        if "=" not in line:
            raise SystemExit(f"{path}:{line_number}: invalid env line without '='")
        key, value = line.split("=", 1)
        env[key.strip()] = value.strip().strip('"').strip("'")
    return env


def is_placeholder(value: str) -> bool:
    lowered = value.strip().lower()
    if not lowered:
        return True
    return any(marker in lowered for marker in PLACEHOLDER_MARKERS)


def require_keys(env: dict[str, str], keys: set[str], errors: list[str], *, allow_placeholders: bool) -> None:
    for key in sorted(keys):
        value = env.get(key, "")
        if key not in env:
            errors.append(f"missing required key: {key}")
            continue
        if not allow_placeholders and is_placeholder(value):
            errors.append(f"{key} must be set to a real non-placeholder value")


def require_mode(env: dict[str, str], key: str, allowed: set[str], errors: list[str]) -> str:
    value = env.get(key, "").strip().lower()
    if value not in allowed:
        errors.append(f"{key} must be one of {sorted(allowed)}, got '{value or '<empty>'}'")
    return value


def validate(env: dict[str, str], *, allow_placeholders: bool) -> list[str]:
    errors: list[str] = []
    require_keys(env, BASE_REQUIRED | SQL_REQUIRED, errors, allow_placeholders=allow_placeholders)

    if env.get("APP_ENV", "").strip().lower() != "production":
        errors.append("APP_ENV must be production for deploy config")

    if env.get("EVENT_PUBLISHER_MODE", "").strip().lower() != "redis":
        errors.append("EVENT_PUBLISHER_MODE must be redis for deploy config")

    if env.get("WHATSAPP_PROVIDER_MODE", "").strip().lower() != "meta":
        errors.append("WHATSAPP_PROVIDER_MODE must be meta for deploy config")

    signature_required = env.get("WHATSAPP_SIGNATURE_REQUIRED", "true").strip().lower()
    if signature_required not in {"true", "false"}:
        errors.append("WHATSAPP_SIGNATURE_REQUIRED must be true or false")
    if signature_required == "true":
        require_keys(env, {"WHATSAPP_APP_SECRET"}, errors, allow_placeholders=allow_placeholders)

    for key in [
        "CONVERSATION_REPOSITORY_MODE",
        "VEHICLE_CACHE_MODE",
        "PLACES_REPOSITORY_MODE",
        "APPOINTMENT_REPOSITORY_MODE",
        "NOTIFICATION_REPOSITORY_MODE",
        "MEDIA_REPOSITORY_MODE",
        "ADMIN_AUDIT_REPOSITORY_MODE",
    ]:
        if env.get(key, "").strip().lower() != "sql":
            errors.append(f"{key} must be sql for deploy config")

    llm_mode = require_mode(env, "LLM_PROVIDER_MODE", {"openai", "deepseek", "groq"}, errors)
    if llm_mode == "openai":
        require_keys(env, {"OPENAI_API_KEY", "OPENAI_LLM_MODEL"}, errors, allow_placeholders=allow_placeholders)
    elif llm_mode == "deepseek":
        require_keys(env, {"DEEPSEEK_API_KEY", "DEEPSEEK_BASE_URL", "DEEPSEEK_MODEL"}, errors, allow_placeholders=allow_placeholders)
    elif llm_mode == "groq":
        require_keys(env, {"GROQ_API_KEY", "GROQ_BASE_URL", "GROQ_MODEL"}, errors, allow_placeholders=allow_placeholders)

    audio_mode = require_mode(env, "MEDIA_AUDIO_PROVIDER_MODE", {"disabled", "openai"}, errors)
    if audio_mode == "openai":
        require_keys(env, {"OPENAI_API_KEY", "OPENAI_AUDIO_TRANSCRIPTION_MODEL"}, errors, allow_placeholders=allow_placeholders)

    image_mode = require_mode(env, "MEDIA_IMAGE_PROVIDER_MODE", {"disabled", "openai", "deepseek", "groq"}, errors)
    if image_mode == "openai":
        require_keys(env, {"OPENAI_API_KEY", "OPENAI_IMAGE_VISION_MODEL"}, errors, allow_placeholders=allow_placeholders)
    elif image_mode == "deepseek":
        require_keys(env, {"DEEPSEEK_API_KEY", "DEEPSEEK_BASE_URL", "DEEPSEEK_IMAGE_MODEL"}, errors, allow_placeholders=allow_placeholders)
    elif image_mode == "groq":
        require_keys(env, {"GROQ_API_KEY", "GROQ_BASE_URL", "GROQ_IMAGE_MODEL"}, errors, allow_placeholders=allow_placeholders)

    runt_mode = require_mode(env, "RUNT_PROVIDER_MODE", {"http", "browser"}, errors)
    if runt_mode == "http":
        require_keys(env, {"RUNT_PROVIDER_API_URL"}, errors, allow_placeholders=allow_placeholders)
    elif runt_mode == "browser":
        require_keys(env, {"CAPTCHA_API_KEY"}, errors, allow_placeholders=allow_placeholders)

    persona_mode = require_mode(env, "RUNT_PERSONA_PROVIDER_MODE", {"http", "disabled", "browser", "local"}, errors)
    if persona_mode == "http":
        require_keys(env, {"RUNT_PERSONA_PROVIDER_API_URL"}, errors, allow_placeholders=allow_placeholders)
    elif persona_mode == "browser":
        require_keys(env, {"CAPTCHA_API_KEY"}, errors, allow_placeholders=allow_placeholders)

    simit_mode = require_mode(env, "SIMIT_PROVIDER_MODE", {"http", "browser"}, errors)
    if simit_mode == "http":
        require_keys(env, {"SIMIT_PROVIDER_API_URL"}, errors, allow_placeholders=allow_placeholders)

    if env.get("NOTIFICATION_WORKER_DISPATCH_OUTBOX", "").strip().lower() == "true":
        require_keys(
            env,
            {"WHATSAPP_ACCESS_TOKEN", "WHATSAPP_PHONE_NUMBER_ID"},
            errors,
            allow_placeholders=allow_placeholders,
        )

    return errors


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--env-file", required=True)
    parser.add_argument("--allow-placeholders", action="store_true")
    args = parser.parse_args()

    env_path = Path(args.env_file)
    if not env_path.exists():
        raise SystemExit(f"Deploy env file not found: {env_path}")

    errors = validate(parse_env(env_path), allow_placeholders=args.allow_placeholders)
    if errors:
        for error in errors:
            print(f"- {error}")
        raise SystemExit("Deploy configuration verification failed.")

    print("Civi deploy configuration verification passed.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
