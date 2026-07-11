from __future__ import annotations

import asyncio
import json
import os
import re
import time
from datetime import datetime, timezone
from typing import Any
from urllib import request as urllib_request

from runt_service.adapters.outbound import captcha as captcha_helpers
from runt_service.adapters.outbound.persona_http_provider import normalize_persona_response
from runt_service.shared.vehicle_analysis import fold
from runt_service.slices.consult_persona.schemas import RuntPersonaRequest, RuntPersonaResponse

RUNT_PERSONA_URL = (
    "https://portalpublico.runt.gov.co/#/consulta-ciudadano-documento/consulta/consulta-ciudadano-documento"
)

_CATEGORY_RE = re.compile(r"\b([ABC]\d)\b", re.IGNORECASE)
_DATE_RE = re.compile(r"\b\d{2}/\d{2}/\d{4}\b")
_LICENSE_STATUS_RE = re.compile(r"\b(ACTIVA|INACTIVA|VENCIDA|CANCELADA)\b", re.IGNORECASE)


# #region agent log
def _agent_log(hypothesis_id: str, location: str, message: str, data: dict[str, Any]) -> None:
    payload = {
        "sessionId": "d9484f",
        "runId": os.getenv("DEBUG_RUN_ID", "post-fix"),
        "hypothesisId": hypothesis_id,
        "location": location,
        "message": message,
        "data": data,
        "timestamp": int(time.time() * 1000),
    }
    line = json.dumps(payload, ensure_ascii=False)
    for path in ("/app/debug-d9484f.log", "/tmp/debug-d9484f.log"):
        try:
            with open(path, "a", encoding="utf-8") as handle:
                handle.write(line + "\n")
        except Exception:
            pass
    body = line.encode("utf-8")
    for base in ("http://host.docker.internal:7684", "http://172.17.0.1:7684"):
        try:
            req = urllib_request.Request(
                f"{base}/ingest/3d764cb1-96d1-4679-8341-8bc3d516e464",
                data=body,
                headers={
                    "Content-Type": "application/json",
                    "X-Debug-Session-Id": "d9484f",
                },
                method="POST",
            )
            urllib_request.urlopen(req, timeout=1.5).read()
            break
        except Exception:
            continue


# #endregion


class BrowserRuntPersonaProvider:
    def __init__(
        self,
        *,
        captcha_api_key: str = "",
        portal_url: str = RUNT_PERSONA_URL,
        timeout_seconds: float = 90.0,
        captcha_retries: int = 5,
        headless: bool = True,
        browser_executable_path: str | None = None,
    ) -> None:
        self.captcha_api_key = (captcha_api_key or "").strip()
        self.portal_url = portal_url.strip() or RUNT_PERSONA_URL
        self.timeout_ms = int(timeout_seconds * 1000)
        self.captcha_retries = max(1, captcha_retries)
        self.headless = headless
        self.browser_executable_path = (browser_executable_path or "").strip() or None
        self._ocr: Any = None

    @classmethod
    def from_env(cls) -> "BrowserRuntPersonaProvider":
        return cls(
            captcha_api_key=os.getenv("CAPTCHA_API_KEY", ""),
            portal_url=os.getenv("RUNT_PERSONA_BROWSER_URL", RUNT_PERSONA_URL),
            timeout_seconds=captcha_helpers.float_env("RUNT_BROWSER_TIMEOUT_SECONDS", default=90.0),
            captcha_retries=captcha_helpers.int_env("RUNT_BROWSER_CAPTCHA_RETRIES", default=5),
            headless=captcha_helpers.bool_env("RUNT_BROWSER_HEADLESS", default=True),
            browser_executable_path=os.getenv("RUNT_BROWSER_EXECUTABLE_PATH", ""),
        )

    async def consult_persona(self, payload: RuntPersonaRequest) -> RuntPersonaResponse:
        documento = "".join(char for char in payload.documento if char.isdigit())
        tipo = (payload.tipoDocumento or "CC").strip().upper() or "CC"
        async with captcha_helpers.BROWSER_LOCK:
            data = await self._consult(documento=documento, tipo_documento=tipo)
        return normalize_persona_response(data, documento=documento, status_code=200)

    async def _consult(self, *, documento: str, tipo_documento: str) -> dict[str, Any]:
        async_playwright = captcha_helpers.load_async_playwright()

        async with async_playwright() as playwright:
            browser = await playwright.chromium.launch(
                headless=self.headless,
                executable_path=self.browser_executable_path,
                args=[
                    "--no-sandbox",
                    "--disable-setuid-sandbox",
                    "--disable-dev-shm-usage",
                    "--disable-blink-features=AutomationControlled",
                    "--window-size=1366,768",
                ],
            )
            page = await browser.new_page(viewport={"width": 1366, "height": 768})
            await page.set_extra_http_headers(
                {
                    "User-Agent": (
                        "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
                        "(KHTML, like Gecko) Chrome/124.0.0.0 Safari/537.36"
                    )
                }
            )
            await page.add_init_script(
                """
                Object.defineProperty(navigator, 'webdriver', { get: () => undefined });
                window.chrome = { runtime: {} };
                """
            )
            try:
                await page.goto(self.portal_url, wait_until="domcontentloaded", timeout=self.timeout_ms)
                await page.locator("input[formcontrolname='documento'], #mat-input-0").first.wait_for(
                    timeout=self.timeout_ms
                )
                await captcha_helpers.select_document_type(page, tipo_documento)
                doc_selector, captcha_selector = await _resolve_persona_inputs(page, timeout_ms=self.timeout_ms)
                await page.locator(captcha_helpers.CAPTCHA_SELECTOR).first.wait_for(timeout=self.timeout_ms)
                await captcha_helpers.set_input_value(page, doc_selector, documento)

                completed = False
                for _ in range(self.captcha_retries):
                    captcha_text = await captcha_helpers.solve_captcha_on_page(
                        page,
                        captcha_api_key=self.captcha_api_key,
                        ocr_holder=self,
                    )
                    if len(captcha_text) < 3:
                        await captcha_helpers.refresh_captcha(page, captcha_input_selector=captcha_selector)
                        continue
                    await captcha_helpers.set_input_value(page, captcha_selector, captcha_text)
                    await page.locator("button.mat-accent, button[type='submit']").first.click(timeout=8000)
                    state = await _wait_for_persona_result(page, timeout_ms=self.timeout_ms)
                    if state["has_not_found"]:
                        raise RuntimeError("Persona no encontrada. Verifique el documento.")
                    if state["has_error"]:
                        await captcha_helpers.refresh_captcha(page, captcha_input_selector=captcha_selector)
                        continue
                    if state["has_results"]:
                        completed = True
                        break

                if not completed:
                    raise RuntimeError("No se pudo completar la consulta RUNT persona con el captcha disponible")

                # Ficha aparece primero; licencias viven en un accordion colapsado.
                # #region agent log
                _agent_log(
                    "H2",
                    "persona_browser_provider.py:pre_wait_licenses",
                    "expanding license accordion after ficha",
                    {"url": page.url},
                )
                # #endregion
                await _wait_for_license_section(page, timeout_ms=min(self.timeout_ms, 30000))

                body_text = await page.locator("body").inner_text(timeout=10000)
                ficha = parse_persona_ficha(body_text)
                # #region agent log
                folded_body = fold(body_text)
                _agent_log(
                    "H2",
                    "persona_browser_provider.py:body",
                    "body markers after consult",
                    {
                        "bodyLen": len(body_text),
                        "hasNombre": bool(ficha.get("nombre")),
                        "hasEstadoPersona": "ESTADO DE LA PERSONA" in folded_body,
                        "hasNroLicencia": "NRO LICENCIA" in folded_body or "NUMERO DE LICENCIA" in folded_body,
                        "hasVerDetalle": "VER DETALLE" in folded_body,
                        "activaCount": folded_body.count("ACTIVA"),
                        "inactivaCount": folded_body.count("INACTIVA"),
                        "tableCount": await page.locator("table, mat-table").count(),
                        "url": page.url,
                    },
                )
                # #endregion
                licencias_dom = await _extract_licencias_from_dom(page)
                licencias = licencias_dom
                if not licencias:
                    licencias = parse_licencias_from_text(body_text)
                # #region agent log
                _agent_log(
                    "H1",
                    "persona_browser_provider.py:licenses",
                    "license extraction counts",
                    {
                        "domCount": len(licencias_dom),
                        "finalCount": len(licencias),
                        "estados": [str(item.get("estado") or "") for item in licencias[:4]],
                        "hasOt": [bool(item.get("ot")) for item in licencias[:4]],
                    },
                )
                # #endregion

                # Prefer opening detail on ACTIVA rows first.
                detail_links = page.locator(
                    "a:has-text('Ver Detalle'), a:has-text('Ver detalle'), "
                    "button:has-text('Ver Detalle'), button:has-text('Ver detalle'), "
                    "span:has-text('Ver Detalle'), td:has-text('Ver Detalle')"
                )
                detail_count = await detail_links.count()
                # #region agent log
                detail_probe = await page.evaluate(
                    """
                    () => {
                      const texts = Array.from(document.querySelectorAll('a,button,span,td'))
                        .map(el => (el.innerText || '').trim())
                        .filter(t => /detalle/i.test(t))
                        .slice(0, 10);
                      return {detailishTexts: texts, linkCount: document.querySelectorAll('a').length};
                    }
                    """
                )
                _agent_log(
                    "H3",
                    "persona_browser_provider.py:detail_links",
                    "ver detalle link probe",
                    {"detailCount": detail_count, **(detail_probe if isinstance(detail_probe, dict) else {})},
                )
                # #endregion
                all_categorias: list[dict[str, Any]] = []
                detail_errors: list[str] = []
                for index in range(detail_count):
                    try:
                        await detail_links.nth(index).click(timeout=5000)
                        await page.wait_for_timeout(1200)
                        detail_text = await _read_detail_text(page)
                        categorias = parse_categorias_detalle(detail_text)
                        if not categorias:
                            categorias = await _extract_categorias_from_dom(page)
                        # #region agent log
                        _agent_log(
                            "H4",
                            "persona_browser_provider.py:detail_click",
                            "detail modal parse",
                            {
                                "index": index,
                                "detailTextLen": len(detail_text or ""),
                                "hasCategoriaWord": "CATEGORIA" in fold(detail_text or ""),
                                "parsedCount": len(categorias),
                                "cats": [str(item.get("categoria") or "") for item in categorias[:4]],
                            },
                        )
                        # #endregion
                        if categorias:
                            all_categorias.extend(categorias)
                            if index < len(licencias):
                                licencias[index]["categorias"] = categorias
                        await _close_detail(page)
                        await page.wait_for_timeout(400)
                    except Exception as exc:
                        detail_errors.append(f"{index}:{type(exc).__name__}")
                        try:
                            await _close_detail(page)
                        except Exception:
                            pass
                        continue

                if licencias and all_categorias and not any(item.get("categorias") for item in licencias):
                    # Attach merged categories to the first ACTIVA license (or first row).
                    target = next(
                        (item for item in licencias if str(item.get("estado") or "").upper() == "ACTIVA"),
                        licencias[0],
                    )
                    target["categorias"] = _dedupe_categories(all_categorias)
                elif not licencias and all_categorias:
                    licencias = [
                        {
                            "numero": documento,
                            "estado": ficha.get("estadoConductor") or "ACTIVA",
                            "ot": None,
                            "categorias": _dedupe_categories(all_categorias),
                        }
                    ]
                elif not licencias:
                    categorias = parse_categorias_detalle(body_text)
                    if categorias:
                        licencias = [
                            {
                                "numero": documento,
                                "estado": ficha.get("estadoConductor") or "ACTIVA",
                                "ot": None,
                                "categorias": categorias,
                            }
                        ]

                payload = build_persona_payload(ficha=ficha, licencias=licencias)
                # #region agent log
                _agent_log(
                    "H5",
                    "persona_browser_provider.py:payload",
                    "final persona payload shape",
                    {
                        "hasNombre": bool(payload.get("nombre")),
                        "licenseCount": len(payload.get("licencias") or []),
                        "categoryCounts": [
                            len(item.get("categorias") or [])
                            for item in (payload.get("licencias") or [])[:4]
                            if isinstance(item, dict)
                        ],
                        "detailErrors": detail_errors[:5],
                        "allCategoriasCount": len(all_categorias),
                    },
                )
                # #endregion
                return payload
            finally:
                await browser.close()


class LocalRuntPersonaProvider:
    async def consult_persona(self, payload: RuntPersonaRequest) -> RuntPersonaResponse:
        documento = "".join(char for char in payload.documento if char.isdigit())
        data = build_local_persona_payload(documento)
        return RuntPersonaResponse(
            ok=True,
            documentoTail=documento[-4:],
            data=data,
            error=None,
            statusCode=200,
            checkedAt=datetime.now(timezone.utc).isoformat(),
        )


def build_local_persona_payload(documento: str) -> dict[str, Any]:
    return {
        "nombre": "Persona Demo Local",
        "estadoPersona": "ACTIVA",
        "estadoConductor": "ACTIVO",
        "nroInscripcion": f"INS-{documento[-6:] or '000000'}",
        "licencias": [
            {
                "numero": documento or "1052838811",
                "estado": "ACTIVA",
                "ot": "OT DEMO LOCAL",
                "categorias": [
                    {
                        "categoria": "A2",
                        "fechaExpedicion": "30/06/2026",
                        "fechaVencimiento": "30/06/2036",
                    },
                    {
                        "categoria": "B1",
                        "fechaExpedicion": "29/11/2024",
                        "fechaVencimiento": "29/11/2034",
                    },
                ],
            }
        ],
    }


def parse_persona_ficha(text: str) -> dict[str, Any]:
    return {
        "nombre": _extract_label(
            text,
            ("nombre completo", "nombre del ciudadano", "nombres y apellidos", "nombre"),
        ),
        "estadoPersona": _normalize_status(
            _extract_label(text, ("estado de la persona", "estado persona", "estado del ciudadano"))
        ),
        "estadoConductor": _normalize_status(
            _extract_label(text, ("estado del conductor", "estado conductor"))
        ),
        "nroInscripcion": _extract_label(
            text,
            ("nro de inscripcion", "numero de inscripcion", "nro. inscripcion", "inscripcion"),
        ),
    }


def parse_licencias_from_text(text: str) -> list[dict[str, Any]]:
    """Parse license rows from portal text (supports one-cell-per-line tables)."""
    licenses: list[dict[str, Any]] = []
    lines = [line.strip() for line in text.replace("\r", "\n").split("\n") if line.strip()]

    # Skip ficha statuses like "ESTADO DE LA PERSONA / ACTIVA" by requiring a nearby license number.
    for index, line in enumerate(lines):
        folded = fold(line)
        if "VER DETALLE" in folded or folded == "DETALLE":
            continue
        status_match = _LICENSE_STATUS_RE.search(line)
        if not status_match:
            continue
        # Ignore persona/conductor status labels (not license rows).
        if any(
            marker in folded
            for marker in ("ESTADO DE LA PERSONA", "ESTADO DEL CONDUCTOR", "ESTADO PERSONA", "ESTADO CONDUCTOR")
        ):
            continue
        if index > 0 and any(
            marker in fold(lines[index - 1])
            for marker in ("ESTADO DE LA PERSONA", "ESTADO DEL CONDUCTOR", "ESTADO PERSONA", "ESTADO CONDUCTOR")
        ):
            continue

        number_match = re.search(r"\b(\d{6,12})\b", line)
        ot = None
        if number_match:
            after_status = line[status_match.end() :].strip(" -|\t")
            if after_status and not _DATE_RE.search(after_status):
                ot = after_status or None
        else:
            # Multiline row: number / OT / date / ESTADO within a small window above.
            window = lines[max(0, index - 6) : index]
            for candidate in reversed(window):
                if number_match is None:
                    found = re.search(r"\b(\d{6,12})\b", candidate)
                    if found:
                        number_match = found
                        continue
                if ot is None and candidate and not _DATE_RE.fullmatch(candidate):
                    if "VER DETALLE" not in fold(candidate) and not _LICENSE_STATUS_RE.search(candidate):
                        if re.search(r"[A-Za-z]", candidate):
                            ot = candidate
            if number_match is None:
                continue

        licenses.append(
            {
                "numero": number_match.group(1),
                "estado": status_match.group(1).upper(),
                "ot": ot,
                "categorias": [],
            }
        )
    return _dedupe_licenses(licenses)


def parse_categorias_detalle(text: str) -> list[dict[str, Any]]:
    categories: list[dict[str, Any]] = []
    lines = [line.strip() for line in text.replace("\r", "\n").split("\n") if line.strip()]
    for index, line in enumerate(lines):
        cat_match = _CATEGORY_RE.search(line)
        if not cat_match:
            continue
        dates = _DATE_RE.findall(line)
        if len(dates) < 2:
            window = " ".join(lines[index : index + 4])
            dates = _DATE_RE.findall(window)
        if len(dates) < 1:
            continue
        categories.append(
            {
                "categoria": cat_match.group(1).upper(),
                "fechaExpedicion": dates[0] if dates else None,
                "fechaVencimiento": dates[1] if len(dates) >= 2 else (dates[0] if dates else None),
            }
        )
    return _dedupe_categories(categories)


async def _extract_licencias_from_dom(page: Any) -> list[dict[str, Any]]:
    rows = await page.evaluate(
        """
        () => {
            const folded = value => (value || '').normalize('NFD').replace(/[\\u0300-\\u036f]/g, '').toUpperCase();
            const tables = Array.from(document.querySelectorAll('table, mat-table'));
            const results = [];
            for (const table of tables) {
                const header = folded(table.innerText || '');
                if (!header.includes('LICENCIA') && !header.includes('NRO LICENCIA') && !header.includes('ESTADO')) {
                    continue;
                }
                const bodyRows = Array.from(table.querySelectorAll('tbody tr, mat-row, tr'));
                for (const row of bodyRows) {
                    const cells = Array.from(row.querySelectorAll('td, mat-cell, th, mat-header-cell'))
                        .map(cell => (cell.innerText || '').trim())
                        .filter(Boolean);
                    if (cells.length < 2) continue;
                    const joined = cells.join(' | ');
                    const statusMatch = joined.match(/\\b(ACTIVA|INACTIVA|VENCIDA|CANCELADA)\\b/i);
                    const numberMatch = joined.match(/\\b(\\d{6,12})\\b/);
                    if (!statusMatch || !numberMatch) continue;
                    if (folded(joined).includes('ESTADO DE LA PERSONA') || folded(joined).includes('ESTADO DEL CONDUCTOR')) {
                        continue;
                    }
                    const ot = cells.find(cell => /[A-Za-z]{3,}/.test(cell) && !/ACTIVA|INACTIVA|VER DETALLE/i.test(cell)) || null;
                    results.push({
                        numero: numberMatch[1],
                        estado: statusMatch[1].toUpperCase(),
                        ot,
                        categorias: []
                    });
                }
            }
            return results;
        }
        """
    )
    if not isinstance(rows, list):
        return []
    return _dedupe_licenses([row for row in rows if isinstance(row, dict)])


async def _extract_categorias_from_dom(page: Any) -> list[dict[str, Any]]:
    rows = await page.evaluate(
        """
        () => {
            const root = document.querySelector('mat-dialog-container, .cdk-overlay-pane') || document.body;
            const tables = Array.from(root.querySelectorAll('table, mat-table'));
            const results = [];
            for (const table of tables) {
                const bodyRows = Array.from(table.querySelectorAll('tbody tr, mat-row, tr'));
                for (const row of bodyRows) {
                    const cells = Array.from(row.querySelectorAll('td, mat-cell'))
                        .map(cell => (cell.innerText || '').trim())
                        .filter(Boolean);
                    if (!cells.length) continue;
                    const joined = cells.join(' ');
                    const cat = joined.match(/\\b([ABC]\\d)\\b/i);
                    const dates = joined.match(/\\b\\d{2}\\/\\d{2}\\/\\d{4}\\b/g) || [];
                    if (!cat || dates.length < 1) continue;
                    results.push({
                        categoria: cat[1].toUpperCase(),
                        fechaExpedicion: dates[0] || null,
                        fechaVencimiento: dates[1] || dates[0] || null
                    });
                }
            }
            return results;
        }
        """
    )
    if not isinstance(rows, list):
        return []
    return _dedupe_categories([row for row in rows if isinstance(row, dict)])


def build_persona_payload(
    *,
    ficha: dict[str, Any],
    licencias: list[dict[str, Any]],
) -> dict[str, Any]:
    return {
        "nombre": ficha.get("nombre"),
        "estadoPersona": ficha.get("estadoPersona"),
        "estadoConductor": ficha.get("estadoConductor"),
        "nroInscripcion": ficha.get("nroInscripcion"),
        "licencias": licencias,
        "success": True,
    }


async def _resolve_persona_inputs(page: Any, *, timeout_ms: int) -> tuple[str, str]:
    await page.locator("input[formcontrolname='documento'], input.mat-input-element, #mat-input-0").first.wait_for(
        timeout=timeout_ms
    )
    for doc_sel, captcha_sel in (
        ("input[formcontrolname='documento']", "input[formcontrolname='captcha']"),
        ("#mat-input-0", "#mat-input-1"),
        ("#mat-input-1", "#mat-input-2"),
    ):
        try:
            if await page.locator(doc_sel).count() and await page.locator(captcha_sel).count():
                return doc_sel, captcha_sel
        except Exception:
            continue
    return "input[formcontrolname='documento']", "input[formcontrolname='captcha']"


async def _wait_for_persona_result(page: Any, *, timeout_ms: int) -> dict[str, bool]:
    deadline = asyncio.get_running_loop().time() + (timeout_ms / 1000)
    while asyncio.get_running_loop().time() < deadline:
        state = await page.evaluate(
            """
            () => {
                const body = (document.body.innerText || '').toLowerCase();
                const url = window.location.href.toLowerCase();
                const hasError = body.includes('captcha') &&
                    (body.includes('incorrecto') || body.includes('invalido') || body.includes('inválido'));
                const hasResults =
                    url.includes('info-ciudadano') ||
                    (url.includes('consulta-ciudadano') && body.includes('licencia')) ||
                    body.includes('estado del conductor') ||
                    body.includes('estado de la persona') ||
                    body.includes('nro de inscripcion') ||
                    body.includes('numero de inscripcion') ||
                    (body.includes('licencia') && (body.includes('activa') || body.includes('inactiva'))) ||
                    body.includes('ver detalle');
                const hasNotFound = body.includes('no se encontr') || body.includes('no existe') ||
                    body.includes('datos incorrectos') || body.includes('sin informacion');
                return {has_error: hasError, has_results: hasResults, has_not_found: hasNotFound};
            }
            """
        )
        if state["has_error"] or state["has_results"] or state["has_not_found"]:
            return state
        await page.wait_for_timeout(250)
    return {"has_error": False, "has_results": False, "has_not_found": False}


_LICENSE_SECTION_TITLES = (
    "Licencia(s) de conducción",
    "Licencias de conducción",
    "Licencia de conducción",
)


async def _expand_persona_section(page: Any) -> bool:
    """Expand the licenses Material accordion (must click the short title node)."""
    for label in _LICENSE_SECTION_TITLES:
        try:
            locator = page.get_by_text(label, exact=True)
            if await locator.count() > 0:
                await locator.first.click(timeout=5_000)
                await page.wait_for_timeout(1500)
                # #region agent log
                _agent_log(
                    "H6",
                    "persona_browser_provider.py:expand_section",
                    "accordion expand via get_by_text",
                    {"clicked": True, "label": label},
                )
                # #endregion
                return True
        except Exception:
            pass

    clicked = await page.evaluate(
        """
        (labels) => {
            const normalize = (value) => (value || '').replace(/\\s+/g, ' ').trim();
            const wanted = new Set(labels.map(normalize));
            const title = Array.from(document.querySelectorAll('.panel-title-text, mat-panel-title'))
                .find((el) => wanted.has(normalize(el.innerText || el.textContent || '')));
            if (!title) return false;
            const clickable = title.closest(
                'mat-expansion-panel-header, .mat-expansion-panel-header, button, [role="button"]'
            ) || title;
            clickable.click();
            return true;
        }
        """,
        list(_LICENSE_SECTION_TITLES),
    )
    # #region agent log
    _agent_log(
        "H6",
        "persona_browser_provider.py:expand_section",
        "accordion expand via panel-title-text",
        {"clicked": bool(clicked)},
    )
    # #endregion
    if clicked:
        await page.wait_for_timeout(1500)
    return bool(clicked)


async def _wait_for_license_section(page: Any, *, timeout_ms: int) -> None:
    """Ficha loads first; licenses sit behind a collapsed accordion until expanded."""
    await _expand_persona_section(page)
    deadline = asyncio.get_running_loop().time() + (timeout_ms / 1000)
    while asyncio.get_running_loop().time() < deadline:
        ready = await page.evaluate(
            """
            () => {
                const body = (document.body.innerText || '').toLowerCase();
                const detailCount = Array.from(document.querySelectorAll('a,button,span,td'))
                    .filter(el => /ver\\s*detalle/i.test((el.innerText || '').trim())).length;
                return {
                    hasDetail: detailCount > 0,
                    detailCount,
                    hasNroLicencia: body.includes('nro licencia') || body.includes('nro. licencia') ||
                        body.includes('numero de licencia') || body.includes('número de licencia'),
                    hasLicenciasHeader: body.includes('licencias') || body.includes('licencia de conduc'),
                };
            }
            """
        )
        # #region agent log
        _agent_log(
            "H2",
            "persona_browser_provider.py:license_section_poll",
            "license section poll",
            dict(ready) if isinstance(ready, dict) else {"ready": ready},
        )
        # #endregion
        if ready.get("hasDetail") or ready.get("hasNroLicencia"):
            await page.wait_for_timeout(500)
            return
        await page.wait_for_timeout(300)
    # #region agent log
    _agent_log(
        "H2",
        "persona_browser_provider.py:license_section_timeout",
        "timed out waiting for license section",
        {"timeoutMs": timeout_ms},
    )
    # #endregion


async def _read_detail_text(page: Any) -> str:
    for selector in (
        "mat-dialog-container",
        ".cdk-overlay-pane",
        "mat-expansion-panel.mat-expanded",
        "body",
    ):
        try:
            locator = page.locator(selector).first
            if await locator.count():
                text = await locator.inner_text(timeout=3000)
                if text and len(text.strip()) > 20:
                    return text
        except Exception:
            continue
    return await page.locator("body").inner_text(timeout=5000)


async def _close_detail(page: Any) -> None:
    for selector in (
        "button:has-text('Cerrar')",
        "button:has-text('Close')",
        "mat-dialog-container button.mat-icon-button",
        ".cdk-overlay-backdrop",
    ):
        try:
            locator = page.locator(selector).first
            if await locator.count():
                await locator.click(timeout=2000)
                await page.wait_for_timeout(400)
                return
        except Exception:
            continue
    try:
        await page.keyboard.press("Escape")
        await page.wait_for_timeout(400)
    except Exception:
        return


def _extract_label(text: str, labels: tuple[str, ...]) -> str | None:
    lines = [line.strip() for line in text.replace("\r", "\n").split("\n") if line.strip()]
    folded_labels = tuple(fold(label) for label in labels)
    for index, line in enumerate(lines):
        folded_line = fold(line)
        if any(label in folded_line for label in folded_labels):
            after_colon = line.split(":", 1)[1].strip() if ":" in line else ""
            if after_colon:
                return after_colon
            if index + 1 < len(lines):
                candidate = lines[index + 1].strip()
                if candidate and not any(fold(label) in fold(candidate) for label in labels):
                    return candidate
    return None


def _normalize_status(value: str | None) -> str | None:
    if not value:
        return None
    match = re.search(r"\b(ACTIVA|ACTIVO|INACTIVA|INACTIVO|VENCIDA|CANCELADA)\b", value, flags=re.IGNORECASE)
    return match.group(1).upper() if match else value.strip().upper()


def _dedupe_licenses(licenses: list[dict[str, Any]]) -> list[dict[str, Any]]:
    seen: set[tuple[str, str]] = set()
    result: list[dict[str, Any]] = []
    for item in licenses:
        numero = str(item.get("numero") or "")
        estado = str(item.get("estado") or "").upper()
        if not numero:
            continue
        key = (numero, estado)
        if key in seen:
            continue
        seen.add(key)
        result.append(item)
    return result


def _dedupe_categories(categories: list[dict[str, Any]]) -> list[dict[str, Any]]:
    seen: set[str] = set()
    result: list[dict[str, Any]] = []
    for item in categories:
        key = str(item.get("categoria") or "")
        if not key or key in seen:
            continue
        seen.add(key)
        result.append(item)
    return result
