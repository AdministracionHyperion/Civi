#!/usr/bin/env python3
from __future__ import annotations

import json
import re
import unicodedata
from pathlib import Path

RAW = Path(__file__).resolve().parents[2] / "data" / "places" / "raw"


def strip_accents(value: str) -> str:
    return "".join(ch for ch in unicodedata.normalize("NFKD", value) if not unicodedata.combining(ch))


def norm_key(value: str) -> str:
    return re.sub(r"\s+", " ", strip_accents(value or "").upper().strip())


def target_key(target: dict) -> str:
    return f"{target.get('kind')}|{norm_key(target.get('department') or '')}|{norm_key(target.get('municipality') or '')}"


def main() -> None:
    progress_path = RAW / "scrape_progress.json"
    progress = json.loads(progress_path.read_text(encoding="utf-8")) if progress_path.exists() else {"completed": [], "failed": []}
    completed = set(progress.get("completed") or [])
    removed = []

    for path in RAW.glob("*.json"):
        if path.name == "scrape_progress.json":
            continue
        data = json.loads(path.read_text(encoding="utf-8"))
        rows = data.get("rows") or []
        uniq = {(row.get("name"), row.get("address"), row.get("nit")) for row in rows}
        count = len(rows)
        if count >= 100 and len(uniq) < count * 0.5:
            key = target_key(data.get("target") or {})
            removed.append((path.name, count, len(uniq), key))
            path.unlink()
            completed.discard(key)

    progress["completed"] = sorted(completed)
    progress["failed"] = []
    progress_path.write_text(json.dumps(progress, ensure_ascii=False, indent=2), encoding="utf-8")
    print("removed:")
    for item in removed:
        print(item)
    print("completed_now", len(completed))


if __name__ == "__main__":
    main()
