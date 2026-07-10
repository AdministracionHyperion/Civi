#!/usr/bin/env python3
"""Mark likely truncated shards (exactly 25 rows) for re-scrape with fixed pagination."""

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
    progress = json.loads(progress_path.read_text(encoding="utf-8"))
    completed = set(progress.get("completed") or [])
    reset = []

    for path in RAW.glob("*.json"):
        if path.name == "scrape_progress.json":
            continue
        data = json.loads(path.read_text(encoding="utf-8"))
        count = int(data.get("count") or len(data.get("rows") or []))
        if count != 25:
            continue
        key = target_key(data.get("target") or {})
        reset.append(key)
        path.unlink()
        completed.discard(key)

    progress["completed"] = sorted(completed)
    progress["failed"] = [f for f in (progress.get("failed") or []) if f.get("key") not in set(reset)]
    progress_path.write_text(json.dumps(progress, ensure_ascii=False, indent=2), encoding="utf-8")
    print(f"reset_for_rescrape={len(reset)}")
    for key in sorted(reset):
        print(key)


if __name__ == "__main__":
    main()
