from __future__ import annotations

import hashlib
import json
import urllib.request
from datetime import datetime, timezone
from pathlib import Path

OUT = Path("services/places-service/data/reference")
URL = "https://www.datos.gov.co/resource/gdxc-w37w.json?$limit=50000"


def main() -> None:
    req = urllib.request.Request(URL, headers={"User-Agent": "civi-places/0.2"})
    with urllib.request.urlopen(req, timeout=90) as response:
        raw = response.read()
    rows = json.loads(raw.decode("utf-8"))
    print("rows", len(rows))
    print("keys", sorted(rows[0].keys()) if rows else None)
    if rows:
        print("sample", rows[0])

    slim: list[dict[str, str]] = []
    seen: set[str] = set()
    for row in rows:
        code = str(row.get("cod_mpio") or row.get("codigo_municipio") or "").strip()
        name = str(row.get("nom_mpio") or row.get("nombre_municipio") or "").strip()
        dept = str(row.get("dpto") or row.get("nombre_departamento") or "").strip()
        dcode = str(row.get("cod_dpto") or row.get("codigo_departamento") or "").strip()
        if not code or not name:
            continue
        if code in seen:
            continue
        seen.add(code)
        slim.append(
            {
                "municipality_code": code.zfill(5) if code.isdigit() else code,
                "municipality": name,
                "department": dept,
                "department_code": dcode.zfill(2) if dcode.isdigit() else dcode,
            }
        )

    OUT.mkdir(parents=True, exist_ok=True)
    meta = {
        "name": "DIVIPOLA municipios",
        "url": "https://www.datos.gov.co/resource/gdxc-w37w.json",
        "fetched_at": datetime.now(timezone.utc).isoformat(),
        "row_count": len(slim),
        "source_row_count": len(rows),
        "sha256": hashlib.sha256(raw).hexdigest(),
        "schema_observed": sorted(rows[0].keys()) if rows else [],
    }
    payload = {"metadata": meta, "municipalities": slim}
    (OUT / "divipola_municipios.json").write_text(
        json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8"
    )
    (OUT / "divipola_metadata.json").write_text(
        json.dumps(meta, ensure_ascii=False, indent=2), encoding="utf-8"
    )
    print("slim", len(slim))
    print("wrote", OUT)


if __name__ == "__main__":
    main()
