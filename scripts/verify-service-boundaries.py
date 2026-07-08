from __future__ import annotations

import ast
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]

SERVICE_PACKAGES = {
    "admin-service": "admin_service",
    "appointment-service": "appointment_service",
    "channel-gateway": "channel_gateway",
    "conversation-service": "conversation_service",
    "bot-orchestrator": "bot_orchestrator",
    "media-service": "media_service",
    "notification-service": "notification_service",
    "knowledge-service": "knowledge_service",
    "places-service": "places_service",
    "runt-service": "runt_service",
    "simit-service": "simit_service",
    "quote-service": "quote_service",
    "billing-service": "billing_service",
    "handoff-service": "handoff_service",
    "vehicle-service": "vehicle_service",
}


def main() -> None:
    failures: list[str] = []
    for service_name, own_package in SERVICE_PACKAGES.items():
        src_root = ROOT / "services" / service_name / "src"
        if not src_root.is_dir():
            failures.append(f"{service_name}: missing src directory")
            continue
        forbidden_packages = {
            package
            for candidate_service, package in SERVICE_PACKAGES.items()
            if candidate_service != service_name
        }
        for file_path in src_root.rglob("*.py"):
            failures.extend(_forbidden_imports(file_path, own_package, forbidden_packages))

    if failures:
        for failure in failures:
            print(failure)
        raise SystemExit("Service boundary verification failed.")

    print("Civi service boundary verification passed.")


def _forbidden_imports(
    file_path: Path,
    own_package: str,
    forbidden_packages: set[str],
) -> list[str]:
    relative_path = file_path.relative_to(ROOT)
    tree = ast.parse(file_path.read_text(encoding="utf-8"), filename=str(relative_path))
    failures: list[str] = []
    for node in ast.walk(tree):
        imported_names: list[str] = []
        if isinstance(node, ast.Import):
            imported_names = [alias.name for alias in node.names]
        elif isinstance(node, ast.ImportFrom) and node.module:
            imported_names = [node.module]
        for imported_name in imported_names:
            root_name = imported_name.split(".", 1)[0]
            if root_name in forbidden_packages:
                failures.append(
                    f"{relative_path}:{node.lineno}: imports foreign service package `{root_name}` "
                    f"from `{own_package}` runtime"
                )
    return failures


if __name__ == "__main__":
    main()
