from __future__ import annotations

import json
from pathlib import Path

import pytest

from places_service.cli import import_catalog


FIXTURE_ROWS = [
    {
        "kind": "CDA",
        "name": "CDA Prueba CLI",
        "nit": "800197268-1",
        "address": "Calle 36 # 15-20",
        "city": "Bucaramanga",
        "department": "Santander",
        "phone": "6076432121",
    }
]


def _write_input(tmp_path: Path) -> Path:
    path = tmp_path / "mini_catalog.json"
    path.write_text(json.dumps(FIXTURE_ROWS), encoding="utf-8")
    return path


def test_import_catalog_requires_mode(tmp_path: Path) -> None:
    input_path = _write_input(tmp_path)
    with pytest.raises(SystemExit):
        import_catalog.main(["--input", str(input_path), "--report-dir", str(tmp_path / "reports")])


def test_import_catalog_dry_run_writes_reports(tmp_path: Path) -> None:
    input_path = _write_input(tmp_path)
    report_dir = tmp_path / "reports"
    rc = import_catalog.main(
        [
            "--input",
            str(input_path),
            "--dry-run",
            "--report-dir",
            str(report_dir),
        ]
    )
    assert rc == 0
    assert (report_dir / "reconciliation.json").exists()
    recon = json.loads((report_dir / "reconciliation.json").read_text(encoding="utf-8"))
    assert recon["sum_matches_input"] is True
    assert recon["unique_sites"] == 1


def test_import_catalog_apply_without_database_url_fails(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    input_path = _write_input(tmp_path)
    monkeypatch.delenv("PLACES_DATABASE_URL", raising=False)
    with pytest.raises(SystemExit) as exc:
        import_catalog.main(
            [
                "--input",
                str(input_path),
                "--apply",
                "--report-dir",
                str(tmp_path / "reports"),
            ]
        )
    assert "refusing to use an implicit SQLite default" in str(exc.value)


def test_import_catalog_modes_are_mutually_exclusive(tmp_path: Path) -> None:
    input_path = _write_input(tmp_path)
    with pytest.raises(SystemExit):
        import_catalog.main(
            [
                "--input",
                str(input_path),
                "--dry-run",
                "--apply",
                "--report-dir",
                str(tmp_path / "reports"),
            ]
        )
