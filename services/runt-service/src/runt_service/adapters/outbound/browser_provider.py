from __future__ import annotations

import asyncio
import base64
import os
import re
from typing import Any

import httpx

from runt_service.adapters.outbound.http_provider import normalize_runt_response
from runt_service.shared.vehicle_analysis import build_vehicle_payload, fold
from runt_service.slices.check_vigencia.schemas import RuntVigenciaRequest, RuntVigenciaResponse

RUNT_URL = "https://portalpublico.runt.gov.co/#/consulta-vehiculo/consulta/consulta-ciudadana"
CAPTCHA_CREATE_TASK_URL = "https://api.anti-captcha.com/createTask"
CAPTCHA_RESULT_URL = "https://api.anti-captcha.com/getTaskResult"
CAPTCHA_SELECTOR = "img.img-captcha, img[alt='Captcha'], img.img-responsive.img-fluid"
_BROWSER_LOCK = asyncio.Semaphore(1)


class BrowserRuntProvider:
    def __init__(
        self,
        *,
        captcha_api_key: str = "",
        portal_url: str = RUNT_URL,
        timeout_seconds: float = 75.0,
        captcha_retries: int = 5,
        headless: bool = True,
        browser_executable_path: str | None = None,
    ) -> None:
        self.captcha_api_key = (captcha_api_key or "").strip()
        self.portal_url = portal_url.strip() or RUNT_URL
        self.timeout_ms = int(timeout_seconds * 1000)
        self.captcha_retries = max(1, captcha_retries)
        self.headless = headless
        self.browser_executable_path = (browser_executable_path or "").strip() or None
        self._ocr: Any = None

    @classmethod
    def from_env(cls) -> "BrowserRuntProvider":
        return cls(
            captcha_api_key=os.getenv("CAPTCHA_API_KEY", ""),
            portal_url=os.getenv("RUNT_BROWSER_URL", RUNT_URL),
            timeout_seconds=_float_env("RUNT_BROWSER_TIMEOUT_SECONDS", default=75.0),
            captcha_retries=_int_env("RUNT_BROWSER_CAPTCHA_RETRIES", default=5),
            headless=_bool_env("RUNT_BROWSER_HEADLESS", default=True),
            browser_executable_path=os.getenv("RUNT_BROWSER_EXECUTABLE_PATH", ""),
        )

    async def check_vigencia(self, payload: RuntVigenciaRequest) -> RuntVigenciaResponse:
        async with _BROWSER_LOCK:
            data = await self._consult(payload)
        return normalize_runt_response(data, fallback_placa=payload.placa.strip().upper())

    async def _consult(self, payload: RuntVigenciaRequest) -> dict[str, Any]:
        async_playwright = _load_async_playwright()
        normalized_plate = payload.placa.strip().upper()
        normalized_document = payload.documento.strip()

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
                await _select_document_type(page, payload.tipo_documento.strip().upper())
                await page.locator("#mat-input-0").wait_for(timeout=self.timeout_ms)
                await page.locator(CAPTCHA_SELECTOR).first.wait_for(timeout=self.timeout_ms)
                await _set_input_value(page, "#mat-input-0", normalized_plate)
                await _set_input_value(page, "#mat-input-1", normalized_document)

                completed = False
                for _ in range(self.captcha_retries):
                    captcha_text = await self._solve_captcha(page)
                    if len(captcha_text) < 3:
                        await _refresh_captcha(page)
                        continue
                    await _set_input_value(page, "#mat-input-2", captcha_text)
                    await page.locator("button.mat-accent, button[type='submit']").first.click(timeout=8000)
                    state = await _wait_for_runt_result(page, timeout_ms=self.timeout_ms)
                    if state["has_not_found"]:
                        raise RuntimeError("Vehiculo no encontrado. Verifique placa y documento.")
                    if state["has_error"]:
                        await _refresh_captcha(page)
                        continue
                    if state["has_results"]:
                        completed = True
                        break

                if not completed:
                    raise RuntimeError("No se pudo completar la consulta RUNT con el captcha disponible")

                await page.locator("mat-expansion-panel").first.wait_for(timeout=10000)
                body_text = await page.locator("body").inner_text(timeout=10000)
                info_general = extract_info_general(body_text)
                soat_text = await _extract_panel_text(page, markers=("soat",), fallback_index=1)
                rtm_text = await _extract_panel_text(
                    page,
                    markers=("tecnico mecanica", "tecnico-mecanica", "rtm", "emisiones"),
                    fallback_index=3,
                )
                return build_vehicle_payload(
                    placa=normalized_plate,
                    info_general=info_general,
                    soat_data=parse_soat_text(soat_text),
                    rtm_data=parse_rtm_text(rtm_text),
                )
            finally:
                await browser.close()

    async def _solve_captcha(self, page: Any) -> str:
        captcha = page.locator(CAPTCHA_SELECTOR).first
        image_bytes = await captcha.screenshot(timeout=10000)

        if self.captcha_api_key:
            try:
                result = await _anti_captcha_solve(image_bytes, self.captcha_api_key)
                if len(result) >= 3:
                    return result
            except Exception:
                pass

        return await _ocr_captcha_solve(image_bytes, self)


def extract_info_general(text: str) -> dict[str, Any]:
    return {
        "fechaMatricula": _extract_date_near(text, ("fecha de matricula inicial", "matricula inicial")),
        "claseVehiculo": _extract_label(text, ("clase de vehiculo", "clase")),
        "propietario": _extract_label(text, ("propietario", "titular")),
        "marca": _extract_label(text, ("marca",)),
        "modelo": _extract_label(text, ("modelo",)),
        "linea": _extract_label(text, ("linea",)),
        "color": _extract_label(text, ("color",)),
        "cilindraje": _extract_label(text, ("cilindraje",)),
        "estado": _extract_label(text, ("estado",)),
        "tipoServicio": _extract_label(text, ("tipo de servicio",)),
    }


def parse_soat_text(text: str) -> dict[str, Any] | None:
    if not text.strip():
        return None
    dates = re.findall(r"\b\d{2}/\d{2}/\d{4}\b", text)
    estado_match = re.search(r"\b(VIGENTE|VENCIDO|CANCELADO)\b", fold(text))
    aseguradora_match = re.search(
        r"\b(AXA\s*COLPATRIA|SURA|BOLIVAR|MAPFRE|ALLIANZ|LIBERTY|SEGUROS\s+[A-Z ]+)\b",
        fold(text),
    )
    poliza_match = re.search(r"\b(\d{6,})\b", text)
    return {
        "fechaVencimiento": dates[2] if len(dates) >= 3 else (dates[-1] if dates else None),
        "estado": estado_match.group(1).upper() if estado_match else None,
        "aseguradora": aseguradora_match.group(1).strip() if aseguradora_match else None,
        "poliza": poliza_match.group(1) if poliza_match else None,
        "textoCompleto": text[:600],
    }


def parse_rtm_text(text: str) -> dict[str, Any]:
    normalized = fold(text)
    no_data = (
        not text.strip()
        or len(text) < 40
        or any(marker in normalized for marker in ("NO HAY", "NO SE ENCONTR", "NO REGISTRA", "SIN INFORMACI"))
    )
    dates = re.findall(r"\b\d{2}/\d{2}/\d{4}\b", text)
    has_yes = bool(re.search(r"(^|\s)SI($|\s)", normalized))
    return {
        "tieneRTMVigente": (not no_data) and has_yes,
        "fechaVencimiento": dates[1] if len(dates) >= 2 and not no_data else (dates[0] if dates and not no_data else None),
        "textoCompleto": text[:600],
    }


async def _select_document_type(page: Any, document_type: str) -> None:
    if not document_type or document_type == "CC":
        return
    try:
        selector = page.locator("mat-select[formcontrolname='tipoDocumento'], #mat-select-4").first
        await selector.wait_for(timeout=8000)
        await selector.click()
        options = page.locator("mat-option")
        count = await options.count()
        for index in range(count):
            option = options.nth(index)
            text = fold(await option.inner_text())
            if document_type in text or (document_type == "CE" and "EXTRANJER" in text):
                await option.click()
                return
        await page.keyboard.press("Escape")
    except Exception:
        return


async def _set_input_value(page: Any, selector: str, value: str) -> None:
    await page.locator(selector).wait_for(timeout=10000)
    await page.eval_on_selector(
        selector,
        """
        (element, value) => {
            element.value = value;
            element.dispatchEvent(new Event('input', { bubbles: true }));
            element.dispatchEvent(new Event('change', { bubbles: true }));
        }
        """,
        value,
    )


async def _anti_captcha_solve(image_bytes: bytes, api_key: str) -> str:
    encoded = base64.b64encode(image_bytes).decode("ascii")
    async with httpx.AsyncClient(timeout=45.0) as client:
        task_response = await client.post(
            CAPTCHA_CREATE_TASK_URL,
            json={
                "clientKey": api_key,
                "task": {
                    "type": "ImageToTextTask",
                    "body": encoded,
                    "phrase": False,
                    "case": True,
                    "numeric": 0,
                    "math": 0,
                    "minLength": 0,
                    "maxLength": 0,
                },
            },
        )
        task_response.raise_for_status()
        task_data = task_response.json()
        if task_data.get("errorId") != 0:
            raise RuntimeError(f"Anti-Captcha createTask failed: {task_data.get('errorCode')}")
        task_id = task_data.get("taskId")

        for _ in range(15):
            await asyncio.sleep(1.5)
            result_response = await client.post(
                CAPTCHA_RESULT_URL,
                json={"clientKey": api_key, "taskId": task_id},
            )
            result_response.raise_for_status()
            result_data = result_response.json()
            if result_data.get("errorId") != 0:
                raise RuntimeError(f"Anti-Captcha getTaskResult failed: {result_data.get('errorCode')}")
            if result_data.get("status") == "ready":
                return re.sub(r"[^A-Za-z0-9]", "", str((result_data.get("solution") or {}).get("text") or ""))
    raise RuntimeError("Anti-Captcha timed out")


async def _ocr_captcha_solve(image_bytes: bytes, provider: BrowserRuntProvider) -> str:
    try:
        if provider._ocr is None:
            from ddddocr import DdddOcr

            provider._ocr = DdddOcr(show_ad=False)
    except ImportError:
        raise RuntimeError("ddddocr is required for OCR captcha fallback")
    result = provider._ocr.classification(image_bytes) or ""
    return re.sub(r"[^A-Za-z0-9]", "", str(result))


async def _refresh_captcha(page: Any) -> None:
    await page.locator(CAPTCHA_SELECTOR).first.click(timeout=5000)
    await page.wait_for_timeout(1000)
    try:
        await _set_input_value(page, "#mat-input-2", "")
    except Exception:
        return


async def _wait_for_runt_result(page: Any, *, timeout_ms: int) -> dict[str, bool]:
    deadline = asyncio.get_running_loop().time() + (timeout_ms / 1000)
    while asyncio.get_running_loop().time() < deadline:
        state = await page.evaluate(
            """
            () => {
                const body = (document.body.innerText || '').toLowerCase();
                const url = window.location.href.toLowerCase();
                const hasError = body.includes('captcha') &&
                    (body.includes('incorrecto') || body.includes('invalido') || body.includes('inválido'));
                const hasResults = url.includes('info-vehiculo') ||
                    document.querySelector('mat-expansion-panel') !== null ||
                    body.includes('fecha de matr') || body.includes('placa:') ||
                    body.includes('propietario') || body.includes('activo');
                const hasNotFound = body.includes('no se encontr') || body.includes('no existe') ||
                    body.includes('datos incorrectos') || body.includes('verifique');
                return {has_error: hasError, has_results: hasResults, has_not_found: hasNotFound};
            }
            """
        )
        if state["has_error"] or state["has_results"] or state["has_not_found"]:
            return state
        await page.wait_for_timeout(250)
    return {"has_error": False, "has_results": False, "has_not_found": False}


async def _extract_panel_text(page: Any, *, markers: tuple[str, ...], fallback_index: int | None = None) -> str:
    await page.evaluate(
        """
        ({markers, fallbackIndex}) => {
            const folded = value => (value || '').normalize('NFD').replace(/[\\u0300-\\u036f]/g, '').toLowerCase();
            const panels = Array.from(document.querySelectorAll('mat-expansion-panel'));
            for (const panel of panels) {
                const title = panel.querySelector('mat-panel-title, .mat-expansion-panel-header-title, mat-panel-description');
                const text = folded(title ? title.textContent : panel.textContent);
                if (markers.some(marker => text.includes(marker))) {
                    const header = panel.querySelector('mat-expansion-panel-header');
                    if (header) header.click();
                    return;
                }
            }
            if (fallbackIndex !== null && panels[fallbackIndex]) {
                const header = panels[fallbackIndex].querySelector('mat-expansion-panel-header');
                if (header) header.click();
            }
        }
        """,
        {"markers": list(markers), "fallbackIndex": fallback_index},
    )
    await page.wait_for_timeout(3000)
    return await page.evaluate(
        """
        ({markers, fallbackIndex}) => {
            const folded = value => (value || '').normalize('NFD').replace(/[\\u0300-\\u036f]/g, '').toLowerCase();
            const panels = Array.from(document.querySelectorAll('mat-expansion-panel'));
            for (const panel of panels) {
                const title = panel.querySelector('mat-panel-title, .mat-expansion-panel-header-title, mat-panel-description');
                const text = folded(title ? title.textContent : panel.textContent);
                if (markers.some(marker => text.includes(marker))) {
                    return panel.innerText || panel.textContent || '';
                }
            }
            const panel = fallbackIndex !== null ? panels[fallbackIndex] : null;
            return panel ? (panel.innerText || panel.textContent || '') : '';
        }
        """,
        {"markers": list(markers), "fallbackIndex": fallback_index},
    )


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
                return lines[index + 1].strip()
    return None


def _extract_date_near(text: str, labels: tuple[str, ...]) -> str | None:
    folded_text = fold(text)
    for label in labels:
        position = folded_text.find(fold(label))
        if position >= 0:
            snippet = text[max(0, position - 20) : position + 180]
            match = re.search(r"\b\d{2}/\d{2}/\d{4}\b", snippet)
            if match:
                return match.group(0)
    match = re.search(r"(matricula|matr)[\s\S]{0,120}(\d{2}/\d{2}/\d{4})", text, flags=re.IGNORECASE)
    return match.group(2) if match else None


def _load_async_playwright() -> Any:
    try:
        from playwright.async_api import async_playwright
    except ImportError as exc:
        raise RuntimeError("playwright is required for RUNT_PROVIDER_MODE=browser") from exc
    return async_playwright


def _float_env(name: str, *, default: float) -> float:
    raw_value = os.getenv(name, "").strip()
    if not raw_value:
        return default
    try:
        return float(raw_value)
    except ValueError:
        return default


def _int_env(name: str, *, default: int) -> int:
    raw_value = os.getenv(name, "").strip()
    if not raw_value:
        return default
    try:
        return int(raw_value)
    except ValueError:
        return default


def _bool_env(name: str, *, default: bool) -> bool:
    raw_value = os.getenv(name, "").strip().lower()
    if not raw_value:
        return default
    return raw_value in {"1", "true", "yes", "si"}