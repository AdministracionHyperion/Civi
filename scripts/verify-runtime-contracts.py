from __future__ import annotations

import importlib
from pathlib import Path
import sys

import yaml
from fastapi.routing import APIRoute


ROOT = Path(__file__).resolve().parents[1]

PYTHON_SERVICES = {
    "admin-service": "admin_service.main",
    "appointment-service": "appointment_service.main",
    "channel-gateway": "channel_gateway.main",
    "conversation-service": "conversation_service.main",
    "bot-orchestrator": "bot_orchestrator.main",
    "media-service": "media_service.main",
    "notification-service": "notification_service.main",
    "knowledge-service": "knowledge_service.main",
    "places-service": "places_service.main",
    "runt-service": "runt_service.main",
    "simit-service": "simit_service.main",
    "quote-service": "quote_service.main",
    "billing-service": "billing_service.main",
    "handoff-service": "handoff_service.main",
    "vehicle-service": "vehicle_service.main",
}

HTTP_METHODS = {"get", "post", "put", "patch", "delete"}


def main() -> None:
    _configure_python_path()
    failures: list[str] = []
    for service_name, module_name in PYTHON_SERVICES.items():
        runtime_routes = _runtime_routes(module_name)
        contract_routes = _contract_routes(service_name)
        missing_in_contract = runtime_routes - contract_routes
        missing_in_runtime = contract_routes - runtime_routes
        for method, path in sorted(missing_in_contract):
            failures.append(f"{service_name}: runtime route {method} {path} is missing from OpenAPI")
        for method, path in sorted(missing_in_runtime):
            failures.append(f"{service_name}: OpenAPI route {method} {path} is missing from runtime")

    if failures:
        for failure in failures:
            print(failure)
        raise SystemExit("Runtime/OpenAPI contract verification failed.")

    print("Civi runtime/OpenAPI route verification passed.")


def _configure_python_path() -> None:
    sys.path.insert(0, str(ROOT / "packages" / "python-common" / "src"))
    for service_path in sorted((ROOT / "services").iterdir()):
        src_path = service_path / "src"
        if src_path.is_dir():
            sys.path.insert(0, str(src_path))


def _runtime_routes(module_name: str) -> set[tuple[str, str]]:
    module = importlib.import_module(module_name)
    app = getattr(module, "app")
    routes: set[tuple[str, str]] = set()
    for route in app.routes:
        if not isinstance(route, APIRoute):
            continue
        for method in route.methods - {"HEAD", "OPTIONS"}:
            routes.add((method.lower(), route.path))
    return routes


def _contract_routes(service_name: str) -> set[tuple[str, str]]:
    contract_path = ROOT / "contracts" / f"{service_name}.openapi.yaml"
    contract = yaml.safe_load(contract_path.read_text(encoding="utf-8"))
    paths = contract.get("paths") or {}
    routes: set[tuple[str, str]] = set()
    for path, operations in paths.items():
        if not isinstance(operations, dict):
            continue
        for method in operations:
            if method in HTTP_METHODS:
                routes.add((method, path))
    return routes


if __name__ == "__main__":
    main()
