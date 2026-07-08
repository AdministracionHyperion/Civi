from __future__ import annotations

import importlib
from pathlib import Path
import sys


ROOT = Path(__file__).resolve().parents[1]

SQL_MODULES = {
    "admin-service": "admin_service.adapters.outbound.sql_audit_repository",
    "appointment-service": "appointment_service.adapters.outbound.sql_repository",
    "conversation-service": "conversation_service.adapters.outbound.sql_repository",
    "media-service": "media_service.adapters.outbound.sql_repository",
    "notification-service": "notification_service.adapters.outbound.sql_repository",
    "places-service": "places_service.adapters.outbound.sql_repository",
    "vehicle-service": "vehicle_service.adapters.outbound.sql_cache_repository",
}

ALLOWED_TABLE_PATTERNS = {
    "admin-service": ("admin_",),
    "appointment-service": ("appointment_", "appointments"),
    "conversation-service": ("conversation_",),
    "media-service": ("media_",),
    "notification-service": ("notification_",),
    "places-service": ("places", "places_"),
    "vehicle-service": ("vehicle_",),
}


def main() -> None:
    _configure_python_path()
    failures: list[str] = []
    owners_by_table: dict[str, str] = {}
    for service_name, module_name in SQL_MODULES.items():
        module = importlib.import_module(module_name)
        metadata = getattr(module, "metadata", None)
        if metadata is None:
            failures.append(f"{service_name}: SQL module does not expose metadata")
            continue
        table_names = sorted(table.name for table in metadata.tables.values())
        if not table_names:
            failures.append(f"{service_name}: SQL metadata declares no tables")
            continue

        allowed_patterns = ALLOWED_TABLE_PATTERNS[service_name]
        for table_name in table_names:
            if not _is_allowed_table(table_name, allowed_patterns):
                failures.append(
                    f"{service_name}: table `{table_name}` does not match allowed ownership patterns "
                    f"{', '.join(allowed_patterns)}"
                )
            previous_owner = owners_by_table.get(table_name)
            if previous_owner is not None:
                failures.append(f"table `{table_name}` is declared by both {previous_owner} and {service_name}")
            owners_by_table[table_name] = service_name

    if failures:
        for failure in failures:
            print(failure)
        raise SystemExit("Data ownership verification failed.")

    print("Civi data ownership verification passed.")


def _configure_python_path() -> None:
    sys.path.insert(0, str(ROOT / "packages" / "python-common" / "src"))
    for service_path in sorted((ROOT / "services").iterdir()):
        src_path = service_path / "src"
        if src_path.is_dir():
            sys.path.insert(0, str(src_path))


def _is_allowed_table(table_name: str, allowed_patterns: tuple[str, ...]) -> bool:
    for pattern in allowed_patterns:
        if pattern.endswith("_") and table_name.startswith(pattern):
            return True
        if table_name == pattern:
            return True
    return False


if __name__ == "__main__":
    main()
