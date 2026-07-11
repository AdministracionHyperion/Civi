from __future__ import annotations

import asyncio
import os
import re
import unicodedata
from typing import Any

from simit_service.adapters.outbound.http_provider import normalize_simit_response
from simit_service.slices.consult_multas.schemas import SimitMultasRequest, SimitMultasResponse

SIMIT_URL = "https://www.fcm.org.co/simit/#/estado-cuenta"
_BROWSER_LOCK = asyncio.Semaphore(1)


class BrowserSimitProvider:
    def __init__(
        self,
        *,
        portal_url: str = SIMIT_URL,
        timeout_seconds: float = 75.0,
        headless: bool = True,
        browser_executable_path: str | None = None,
    ) -> None:
        self.portal_url = portal_url.strip() or SIMIT_URL
        self.timeout_ms = int(timeout_seconds * 1000)
        self.headless = headless
        self.browser_executable_path = (browser_executable_path or "").strip() or None

    @classmethod
    def from_env(cls) -> "BrowserSimitProvider":
        return cls(
            portal_url=os.getenv("SIMIT_BROWSER_URL", SIMIT_URL),
            timeout_seconds=_float_env("SIMIT_BROWSER_TIMEOUT_SECONDS", default=75.0),
            headless=_bool_env("SIMIT_BROWSER_HEADLESS", default=True),
            browser_executable_path=os.getenv("SIMIT_BROWSER_EXECUTABLE_PATH", ""),
        )

    async def consult_multas(self, payload: SimitMultasRequest) -> SimitMultasResponse:
        async with _BROWSER_LOCK:
            data = await self._consult(payload)
        return normalize_simit_response(data, fallback_documento=payload.documento)

    async def _consult(self, payload: SimitMultasRequest) -> dict[str, Any]:
        async_playwright = _load_async_playwright()
        query = _normalize_simit_query(payload.documento)

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
                await page.goto(self.portal_url, wait_until="networkidle", timeout=self.timeout_ms)
                await page.locator("#txtBusqueda").wait_for(timeout=self.timeout_ms)
                await page.locator("#txtBusqueda").fill(query, timeout=10000)
                await page.locator("#btnNumDocPlaca").click(timeout=10000)
                state = await _wait_for_simit_result(page, timeout_ms=self.timeout_ms)
                if state["has_error"]:
                    raise RuntimeError("El portal SIMIT reporto un error al realizar la consulta")

                body_text = await page.locator("body").inner_text(timeout=10000)
                details = await _extract_tables(page)
                return {"success": True, "documento": query, **parse_simit_text(body_text, details=details)}
            finally:
                await browser.close()


def parse_simit_text(text: str, *, details: list[dict[str, object]] | None = None) -> dict[str, Any]:
    normalized = fold(text)
    comparendos = _summary_count(text, "Comparendos")
    multas = _summary_count(text, "Multas")
    acuerdos = _summary_count(text, "Acuerdos de pago")
    total = _money_value(_extract_total(text))
    no_fines = "NO TIENES COMPARENDOS" in normalized or "NO POSEE A LA FECHA PENDIENTES" in normalized
    has_fines = (comparendos + multas + total) > 0 and not no_fines
    mensaje = "No se encontro mensaje descriptivo."
    if no_fines:
        mensaje = "El ciudadano no posee a la fecha pendientes de pago por concepto de multas e infracciones."
    elif has_fines:
        mensaje = "El ciudadano presenta multas activas en el SIMIT."

    return {
        "resumen": {
            "comparendos": comparendos,
            "multas": multas,
            "acuerdosPago": acuerdos,
            "total": total,
        },
        "tieneMultas": has_fines,
        "mensaje": mensaje,
        "detalles": details or [],
    }


async def _wait_for_simit_result(page: Any, *, timeout_ms: int) -> dict[str, bool]:
    deadline = asyncio.get_running_loop().time() + (timeout_ms / 1000)
    while asyncio.get_running_loop().time() < deadline:
        state = await page.evaluate(
            """
            () => {
                const body = (document.body.innerText || '').toLowerCase();
                const hasSummary = body.includes('resumen') && body.includes('comparendos');
                const noFines = body.includes('no tienes comparendos') ||
                    body.includes('no posee a la fecha pendientes');
                const hasError = body.includes('error al consultar') || body.includes('ocurrió un error') ||
                    body.includes('ocurrio un error');
                return {has_summary: hasSummary, no_fines: noFines, has_error: hasError};
            }
            """
        )
        if state["has_summary"] or state["no_fines"] or state["has_error"]:
            return state
        await page.wait_for_timeout(250)
    return {"has_summary": False, "no_fines": False, "has_error": False}


async def _extract_tables(page: Any) -> list[dict[str, object]]:
    tables = await page.evaluate(
        """
        () => {
            const output = [];
            document.querySelectorAll('table').forEach(table => {
                const headers = Array.from(table.querySelectorAll('th')).map(th => th.innerText.trim());
                table.querySelectorAll('tbody tr').forEach(tr => {
                    const cols = Array.from(tr.querySelectorAll('td')).map(td => td.innerText.trim());
                    if (!cols.length) return;
                    if (headers.length === cols.length) {
                        const row = {};
                        headers.forEach((header, index) => { row[header || `col_${index}`] = cols[index]; });
                        output.push(row);
                    } else {
                        const row = {};
                        cols.forEach((value, index) => { row[`col_${index}`] = value; });
                        output.push(row);
                    }
                });
            });
            return output;
        }
        """
    )
    return [dict(item) for item in tables if isinstance(item, dict)]


def _summary_count(text: str, label: str) -> int:
    pattern = re.compile(rf"{re.escape(label)}\s*:\s*(\d+)", re.IGNORECASE)
    match = pattern.search(text)
    return int(match.group(1)) if match else 0


def _extract_total(text: str) -> str:
    match = re.search(r"Total\s*:\s*\$?\s*([\d\.,]+)", text, flags=re.IGNORECASE)
    return match.group(1) if match else "0"


def _money_value(value: Any) -> int:
    digits = re.sub(r"[^\d-]", "", str(value or ""))
    if not digits or digits == "-":
        return 0
    try:
        return int(digits)
    except ValueError:
        return 0


def fold(value: str) -> str:
    without_accents = unicodedata.normalize("NFKD", value).encode("ascii", "ignore").decode("ascii")
    return re.sub(r"\s+", " ", without_accents).strip().upper()


def _load_async_playwright() -> Any:
    try:
        from playwright.async_api import async_playwright
    except ImportError as exc:
        raise RuntimeError("playwright is required for SIMIT_PROVIDER_MODE=browser") from exc
    return async_playwright


def _float_env(name: str, *, default: float) -> float:
    raw_value = os.getenv(name, "").strip()
    if not raw_value:
        return default
    try:
        return float(raw_value)
    except ValueError:
        return default


def _bool_env(name: str, *, default: bool) -> bool:
    raw_value = os.getenv(name, "").strip().lower()
    if not raw_value:
        return default
    return raw_value in {"1", "true", "yes", "si"}


_PLATE_QUERY_RE = re.compile(r"^[A-Z]{3}\d{2}[A-Z0-9]$|^[A-Z]{3}\d{3}$", re.IGNORECASE)


def _normalize_simit_query(value: str) -> str:
    """SIMIT search box accepts document number or plate."""
    compact = "".join(char for char in (value or "").strip().upper() if char.isalnum())
    if not compact:
        return ""
    if _PLATE_QUERY_RE.match(compact):
        return compact
    digits = "".join(char for char in compact if char.isdigit())
    return digits or compact
