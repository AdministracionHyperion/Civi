"""Validate places national catalog import against a real PostgreSQL container."""

from __future__ import annotations

import hashlib
import json
import os
import subprocess
import time
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
RAW = ROOT / "services" / "places-service" / "data" / "raw" / "places_colombia_original.json"
REPORT = ROOT / "services" / "places-service" / "data" / "reports" / "postgresql_validation_report.json"
CONTAINER = "civi-places-pg-validation"
PORT = "55432"
DB_URL = f"postgresql+psycopg://civi:civi@127.0.0.1:{PORT}/civi"


def _run(cmd: list[str], *, check: bool = True, env: dict | None = None) -> subprocess.CompletedProcess:
    return subprocess.run(cmd, cwd=str(ROOT), check=check, text=True, capture_output=True, env=env)


def main() -> int:
    report: dict = {"started": True, "container": CONTAINER, "database_url": DB_URL, "steps": []}
    try:
        _run(["docker", "rm", "-f", CONTAINER], check=False)
        _run(
            [
                "docker",
                "run",
                "-d",
                "--name",
                CONTAINER,
                "-e",
                "POSTGRES_USER=civi",
                "-e",
                "POSTGRES_PASSWORD=civi",
                "-e",
                "POSTGRES_DB=civi",
                "-p",
                f"{PORT}:5432",
                "postgres:16-alpine",
            ]
        )
        report["steps"].append({"docker_run": "ok"})

        # Wait for readiness
        for i in range(40):
            probe = _run(
                ["docker", "exec", CONTAINER, "pg_isready", "-U", "civi", "-d", "civi"],
                check=False,
            )
            if probe.returncode == 0:
                break
            time.sleep(1)
        else:
            raise RuntimeError("postgres not ready")
        report["steps"].append({"pg_isready": "ok"})

        env = os.environ.copy()
        env["PYTHONPATH"] = str(ROOT / "services" / "places-service" / "src") + os.pathsep + str(
            ROOT / "packages" / "python-common" / "src"
        )
        env["PLACES_DATABASE_URL"] = DB_URL

        # First apply
        first = _run(
            [
                "python",
                "-m",
                "places_service.cli.import_catalog",
                "--input",
                str(RAW),
                "--apply",
                "--database-url",
                DB_URL,
                "--report-dir",
                str(ROOT / "services" / "places-service" / "data" / "reports"),
            ],
            env=env,
        )
        report["steps"].append({"first_apply_stdout_tail": first.stdout[-1200:]})
        # Second apply
        second = _run(
            [
                "python",
                "-m",
                "places_service.cli.import_catalog",
                "--input",
                str(RAW),
                "--apply",
                "--database-url",
                DB_URL,
                "--report-dir",
                str(ROOT / "services" / "places-service" / "data" / "reports"),
            ],
            env=env,
        )
        report["steps"].append({"second_apply_stdout_tail": second.stdout[-1200:]})

        # Parse last JSON object from second stdout for counts
        def _last_json(text: str) -> dict:
            chunks = []
            buf = []
            depth = 0
            for line in text.splitlines():
                if "{" in line or depth:
                    buf.append(line)
                    depth += line.count("{") - line.count("}")
                    if depth == 0 and buf:
                        chunks.append("\n".join(buf))
                        buf = []
            return json.loads(chunks[-1]) if chunks else {}

        first_counts = _last_json(first.stdout)
        second_counts = _last_json(second.stdout)
        report["first_apply"] = {
            "inserted": first_counts.get("inserted"),
            "updated": first_counts.get("updated"),
            "unchanged": first_counts.get("unchanged"),
        }
        report["second_apply"] = {
            "inserted": second_counts.get("inserted"),
            "updated": second_counts.get("updated"),
            "unchanged": second_counts.get("unchanged"),
        }
        report["sha256"] = hashlib.sha256(RAW.read_bytes()).hexdigest()
        report["passed"] = (
            report["second_apply"].get("inserted") == 0
            and report["second_apply"].get("updated") == 0
            and int(report["second_apply"].get("unchanged") or 0) > 0
            and report["sha256"].startswith("457b4fda")
        )
    except Exception as exc:  # noqa: BLE001
        report["passed"] = False
        report["error"] = str(exc)
    finally:
        _run(["docker", "rm", "-f", CONTAINER], check=False)
        report["container_removed"] = True

    REPORT.parent.mkdir(parents=True, exist_ok=True)
    REPORT.write_text(json.dumps(report, ensure_ascii=False, indent=2), encoding="utf-8")
    print(json.dumps({"passed": report.get("passed"), "path": str(REPORT), "second_apply": report.get("second_apply")}, indent=2))
    return 0 if report.get("passed") else 1


if __name__ == "__main__":
    raise SystemExit(main())
