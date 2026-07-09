#!/usr/bin/env python3
"""Scrape RUNT Directorio de Actores for CDA/CEA/CRC/CIA (no geocoding).

Strategy:
1. Use datos.gov.co open dataset to discover (tipo, departamento, municipio) combos.
2. Query RUNT directory per combo (municipio is required by the form).
3. Persist raw JSON shards under data/places/raw/ (resumable, $0 API cost).
"""

from __future__ import annotations

import argparse
import json
import re
import time
import unicodedata
import urllib.parse
import urllib.request
from datetime import datetime, timezone
from pathlib import Path

from playwright.sync_api import sync_playwright

ROOT = Path(__file__).resolve().parents[2]
RAW_DIR = ROOT / "data" / "places" / "raw"
PROGRESS_PATH = RAW_DIR / "scrape_progress.json"

KIND_TO_TIPO = {
    "CRC": "2",  # Centros de Reconocimiento de Conductores
    "CDA": "3",  # Centros de Diagnóstico Automotor
    "CEA": "4",  # Centros de Enseñanza Automovilística
    "CIA": "7",  # Centros Integrales de Atención
}

OPEN_DATA_URL = "https://www.datos.gov.co/resource/epfm-5fhb.json"


def _strip_accents(value: str) -> str:
    return "".join(
        ch for ch in unicodedata.normalize("NFKD", value) if not unicodedata.combining(ch)
    )


def _norm_key(value: str) -> str:
    return re.sub(r"\s+", " ", _strip_accents(value or "").upper().strip())


def fetch_open_data_targets(kinds: list[str]) -> list[dict]:
    """Return unique tipo/departamento/municipio targets from open data."""
    targets: dict[tuple[str, str, str], dict] = {}
    offset = 0
    page_size = 50000
    kinds_set = set(kinds)
    while True:
        params = {
            "$limit": str(page_size),
            "$offset": str(offset),
            "$where": "tipo_actor in ('CDA','CEA','CRC','CIA')",
        }
        url = OPEN_DATA_URL + "?" + urllib.parse.urlencode(params)
        with urllib.request.urlopen(url, timeout=120) as response:
            batch = json.load(response)
        if not batch:
            break
        for row in batch:
            tipo = str(row.get("tipo_actor") or "").strip().upper()
            if tipo not in kinds_set:
                continue
            depto = str(row.get("nombre_departamento") or "").strip()
            muni = str(row.get("nombre_municipio") or "").strip()
            if not depto or not muni:
                continue
            key = (tipo, _norm_key(depto), _norm_key(muni))
            targets[key] = {
                "kind": tipo,
                "department": depto,
                "municipality": muni,
                "department_code": str(row.get("codigo_departamento") or "").strip(),
            }
        print(f"[open-data] fetched {len(batch)} rows (offset={offset}), targets={len(targets)}")
        if len(batch) < page_size:
            break
        offset += page_size
    return sorted(targets.values(), key=lambda t: (t["kind"], t["department"], t["municipality"]))


def _load_progress() -> dict:
    if PROGRESS_PATH.exists():
        return json.loads(PROGRESS_PATH.read_text(encoding="utf-8"))
    return {"completed": [], "failed": []}


def _save_progress(progress: dict) -> None:
    RAW_DIR.mkdir(parents=True, exist_ok=True)
    PROGRESS_PATH.write_text(json.dumps(progress, ensure_ascii=False, indent=2), encoding="utf-8")


def _target_key(target: dict) -> str:
    return f"{target['kind']}|{_norm_key(target['department'])}|{_norm_key(target['municipality'])}"


def _shard_path(target: dict) -> Path:
    safe = re.sub(r"[^A-Za-z0-9_-]+", "_", _target_key(target))
    return RAW_DIR / f"{safe}.json"


def _match_option(options: list[dict], wanted: str) -> str | None:
    wanted_n = _norm_key(wanted)
    # exact
    for opt in options:
        if _norm_key(opt["t"]) == wanted_n:
            return opt["v"]
    # municipality labels often look like "BUCARAMANGA - SANTANDER"
    for opt in options:
        t = _norm_key(opt["t"]).split(" - ")[0].strip()
        if t == wanted_n:
            return opt["v"]
    # fuzzy contains (avoid matching NORTE DE SANTANDER when wanting SANTANDER at dept level:
    # callers should prefer exact first; this is fallback)
    for opt in options:
        t = _norm_key(opt["t"])
        t_city = t.split(" - ")[0].strip()
        if wanted_n in t_city or t_city in wanted_n:
            return opt["v"]
    # accent / ñ variants already stripped by _norm_key; also try without spaces
    wanted_compact = wanted_n.replace(" ", "")
    for opt in options:
        t_city = _norm_key(opt["t"]).split(" - ")[0].strip().replace(" ", "")
        if t_city == wanted_compact or wanted_compact in t_city or t_city in wanted_compact:
            return opt["v"]
    return None


def _parse_rows(page) -> list[dict]:
    return page.evaluate(
        """() => {
      const rows = [...document.querySelectorAll('article.node--type-actor, article, .views-row')]
        .filter((el, idx, arr) => arr.indexOf(el) === idx);
      const seen = new Set();
      const out = [];
      for (const row of rows) {
        const text = (row.innerText || '').trim();
        if (!text || (!text.includes('NIT') && !/DIRECCI/i.test(text))) continue;
        const name = (row.querySelector('.field--name-title, h2, h3') || {}).innerText?.trim() || '';
        if (!name || seen.has(name + '|' + text.slice(0, 80))) continue;
        seen.add(name + '|' + text.slice(0, 80));
        const grab = (label) => {
          const re = new RegExp(label + '\\\\s*\\\\n\\\\s*([^\\\\n]+)', 'i');
          const m = text.match(re);
          return m ? m[1].trim() : '';
        };
        const lines = text.split('\\n').map(l => l.trim()).filter(Boolean);
        let city_line = '';
        let address = grab('DIRECCI[OÓ]N');
        for (let i = 0; i < lines.length; i++) {
          if (/^DIRECCI/i.test(lines[i])) {
            // next non-empty line is address if grab failed; city is usually two lines after label
            if (!address && lines[i+1] && !/^(NIT|TEL)/i.test(lines[i+1])) address = lines[i+1];
            // Prefer "CIUDAD - DEPARTAMENTO" pattern after address
            for (let j = i + 1; j < Math.min(i + 5, lines.length); j++) {
              if (lines[j].includes(' - ') && !/DIRECCI|NIT|TEL/i.test(lines[j])) {
                city_line = lines[j];
                break;
              }
            }
            break;
          }
        }
        out.push({
          name,
          kind_label: lines[1] || '',
          nit: grab('NIT'),
          phone: grab('TEL[EÉ]FONO'),
          address,
          city_line,
          raw_text: text,
        });
      }
      return out;
    }"""
    )


def scrape_target(page, target: dict, *, delay_s: float) -> list[dict]:
    page.goto("https://www.runt.gov.co/directorio-de-actores", wait_until="domcontentloaded", timeout=90000)
    page.wait_for_selector("#edit-tipo", timeout=30000)
    tipo_value = KIND_TO_TIPO[target["kind"]]
    page.select_option("#edit-tipo", tipo_value)
    page.wait_for_timeout(600)

    dept_options = page.evaluate(
        """() => [...document.querySelectorAll('#edit-departamento option')]
            .map(o => ({v: o.value, t: o.text.trim()}))
            .filter(o => o.v && o.v !== 'All')"""
    )
    dept_value = _match_option(dept_options, target["department"])
    if not dept_value and target.get("department_code"):
        # try code match
        for opt in dept_options:
            if opt["v"] == str(target["department_code"]):
                dept_value = opt["v"]
                break
    if not dept_value:
        raise RuntimeError(f"department not found: {target['department']}")
    page.select_option("#edit-departamento", dept_value)
    page.wait_for_timeout(1200)

    muni_options = page.evaluate(
        """() => [...document.querySelectorAll('#edit-municipio option')]
            .map(o => ({v: o.value, t: o.text.trim()}))
            .filter(o => o.v && o.v !== 'All')"""
    )
    muni_value = _match_option(muni_options, target["municipality"])
    if not muni_value:
        raise RuntimeError(f"municipality not found: {target['municipality']} in {target['department']}")
    page.select_option("#edit-municipio", muni_value)
    page.wait_for_timeout(300)

    page.click("#edit-submit-directorio-de-actores")
    page.wait_for_load_state("domcontentloaded")
    page.wait_for_timeout(2500)

    rows = _parse_rows(page)
    # pagination: follow next href (click often fails / loops due to sticky header + captcha URL)
    page_guard = 0
    seen_signatures: set[str] = {
        f"{row.get('name')}|{row.get('address')}|{row.get('nit')}" for row in rows
    }
    while page_guard < 40:
        href = page.evaluate(
            """() => {
              const a = document.querySelector('.pager__item--next a, li.pager-next a, a[rel="next"]');
              return a ? a.getAttribute('href') : null;
            }"""
        )
        if not href:
            break
        if href.startswith("/"):
            next_url = "https://www.runt.gov.co" + href
        elif href.startswith("http"):
            next_url = href
        else:
            next_url = "https://www.runt.gov.co/" + href.lstrip("./")
        before_url = page.url
        page.goto(next_url, wait_until="domcontentloaded", timeout=90000)
        page.wait_for_timeout(2000)
        if page.url == before_url:
            break
        page_rows = _parse_rows(page)
        new_rows = []
        for row in page_rows:
            sig = f"{row.get('name')}|{row.get('address')}|{row.get('nit')}"
            if sig in seen_signatures:
                continue
            seen_signatures.add(sig)
            new_rows.append(row)
        if not new_rows:
            break
        rows.extend(new_rows)
        page_guard += 1

    time.sleep(delay_s)
    return rows


def main() -> int:
    parser = argparse.ArgumentParser(description="Scrape RUNT places without geocoding")
    parser.add_argument("--kinds", default="CDA,CEA,CRC,CIA")
    parser.add_argument("--limit-targets", type=int, default=0, help="0 = all")
    parser.add_argument("--delay", type=float, default=0.8)
    parser.add_argument("--headful", action="store_true")
    parser.add_argument("--department", default="", help="Filter one department name")
    args = parser.parse_args()

    kinds = [k.strip().upper() for k in args.kinds.split(",") if k.strip()]
    RAW_DIR.mkdir(parents=True, exist_ok=True)

    print("[phase1] discovering targets from datos.gov.co (no Google cost)...")
    targets = fetch_open_data_targets(kinds)
    if args.department:
        dep_n = _norm_key(args.department)
        # Exact department match (avoid "Santander" matching "Norte de Santander")
        targets = [t for t in targets if _norm_key(t["department"]) == dep_n]
    if args.limit_targets > 0:
        targets = targets[: args.limit_targets]
    print(f"[phase1] targets to scrape: {len(targets)}")

    progress = _load_progress()
    completed = set(progress.get("completed") or [])
    failed = progress.get("failed") or []

    with sync_playwright() as playwright:
        browser = playwright.chromium.launch(headless=not args.headful)
        context = browser.new_context(
            locale="es-CO",
            user_agent=(
                "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
                "(KHTML, like Gecko) Chrome/122.0.0.0 Safari/537.36"
            ),
        )
        page = context.new_page()

        for idx, target in enumerate(targets, start=1):
            key = _target_key(target)
            shard = _shard_path(target)
            if key in completed and shard.exists():
                print(f"[{idx}/{len(targets)}] skip {key}")
                continue
            try:
                print(f"[{idx}/{len(targets)}] scrape {key}")
                rows = scrape_target(page, target, delay_s=args.delay)
                payload = {
                    "scraped_at": datetime.now(timezone.utc).isoformat(),
                    "source": "runt_directorio",
                    "target": target,
                    "count": len(rows),
                    "rows": rows,
                }
                shard.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")
                completed.add(key)
                progress["completed"] = sorted(completed)
                progress["failed"] = [f for f in failed if f.get("key") != key]
                _save_progress(progress)
                print(f"  -> {len(rows)} places")
            except Exception as exc:  # noqa: BLE001
                print(f"  !! failed: {exc}")
                failed = [f for f in failed if f.get("key") != key]
                failed.append({"key": key, "error": str(exc), "at": datetime.now(timezone.utc).isoformat()})
                progress["failed"] = failed
                _save_progress(progress)
                # recover page state
                try:
                    page.goto("https://www.runt.gov.co/directorio-de-actores", wait_until="domcontentloaded")
                except Exception:
                    pass

        browser.close()

    print(f"[phase1] done. completed={len(completed)} failed={len(progress.get('failed') or [])}")
    print(f"[phase1] raw shards in {RAW_DIR}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
