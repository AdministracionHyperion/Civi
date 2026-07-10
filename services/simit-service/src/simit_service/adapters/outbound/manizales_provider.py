from __future__ import annotations

import asyncio
import os
import re
from typing import Any

from simit_service.adapters.outbound.http_provider import normalize_simit_response
from simit_service.slices.consult_multas.schemas import SimitMultasRequest, SimitMultasResponse

MANIZALES_URL = "https://www.movilidadmanizales.com.co/portal-servicios/"
_BROWSER_LOCK = asyncio.Semaphore(1)

INFRACTION_CODE_RE = re.compile(r"\b([A-E]\d{2})\b", re.IGNORECASE)
PLATE_RE = re.compile(r"\b([A-Z]{3}\d{3}|[A-Z]{3}\d{2}[A-Z])\b", re.IGNORECASE)
STATUS_RE = re.compile(
    r"\b(Audiencia|Pendiente|Pagad[oa]|En mora|Notificad[oa]|Impugnaci[oó]n|Liquidaci[oó]n)\b",
    re.IGNORECASE,
)
DATE_RE = re.compile(
    r"(?:(?:lunes|martes|mi[eé]rcoles|jueves|viernes|s[aá]bado|domingo)\s+)?"
    r"(?:\d{1,2}\s+de\s+(?:enero|febrero|marzo|abril|mayo|junio|julio|agosto|septiembre|octubre|noviembre|diciembre)"
    r"\s+(?:de\s+)?\d{4}|\d{1,2}[/-]\d{1,2}[/-]\d{2,4})",
    re.IGNORECASE,
)
HEADER_LABELS = {
    "INFRACCION",
    "DESCRIPCION",
    "PLACA O DOCUMENTO",
    "ESTADO",
    "VALOR MULTA",
    "TOTAL A PAGAR",
    "SELECCIONAR",
    "DETALLE FOTODETECCION",
    "DETALLE",
}


class BrowserManizalesProvider:
    def __init__(
        self,
        *,
        portal_url: str = MANIZALES_URL,
        timeout_seconds: float = 75.0,
        headless: bool = True,
        browser_executable_path: str | None = None,
    ) -> None:
        self.portal_url = portal_url.strip() or MANIZALES_URL
        self.timeout_ms = int(timeout_seconds * 1000)
        self.headless = headless
        self.browser_executable_path = (browser_executable_path or "").strip() or None

    @classmethod
    def from_env(cls) -> "BrowserManizalesProvider":
        return cls(
            portal_url=os.getenv("MANIZALES_BROWSER_URL", MANIZALES_URL),
            timeout_seconds=_float_env("MANIZALES_BROWSER_TIMEOUT_SECONDS", default=75.0),
            headless=_bool_env("MANIZALES_BROWSER_HEADLESS", default=True),
            browser_executable_path=os.getenv("MANIZALES_BROWSER_EXECUTABLE_PATH", "")
            or os.getenv("SIMIT_BROWSER_EXECUTABLE_PATH", ""),
        )

    async def consult_multas(self, payload: SimitMultasRequest) -> SimitMultasResponse:
        async with _BROWSER_LOCK:
            data = await self._consult(payload)
        return normalize_simit_response(data, fallback_documento=payload.documento)

    async def _consult(self, payload: SimitMultasRequest) -> dict[str, Any]:
        async_playwright = _load_async_playwright()
        documento = _normalize_query(payload.documento)
        if not documento:
            raise RuntimeError("Documento o placa vacios para consulta Manizales")

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
            try:
                query = documento
                result_url = (
                    "https://www.movilidadmanizales.com.co/portal-servicios/"
                    f"#/resultado-home-public//{query}/0/"
                )
                # Deep-link is the same route the home search uses; more reliable than
                # driving the Angular #busqueda control under Playwright.
                await page.goto(result_url, wait_until="domcontentloaded", timeout=self.timeout_ms)
                await page.wait_for_timeout(1500)
                await _dismiss_overlays(page)
                # If the SPA bounced to home, fall back to filling the search box.
                if "resultado-home-public" not in (page.url or ""):
                    await page.goto(self.portal_url, wait_until="domcontentloaded", timeout=self.timeout_ms)
                    await page.wait_for_timeout(1500)
                    await _dismiss_overlays(page)
                    filled = await _fill_search(page, query)
                    if not filled:
                        await page.goto(result_url, wait_until="domcontentloaded", timeout=self.timeout_ms)
                await _wait_for_results(page, timeout_ms=self.timeout_ms)
                body_text = await page.locator("body").inner_text(timeout=10000)
                table_rows = await _extract_tables(page)
                return {
                    "success": True,
                    "documento": documento,
                    **parse_manizales_text(body_text, details=table_rows),
                }
            finally:
                await browser.close()


def parse_manizales_text(
    text: str,
    *,
    details: list[dict[str, object]] | None = None,
) -> dict[str, Any]:
    normalized = _fold(text)
    explicit_details = [dict(item) for item in (details or []) if isinstance(item, dict)]
    inferred_details = _infer_details_from_text(text)
    merged = _merge_details(explicit_details, inferred_details)

    total = _extract_payable_total(text)
    labeled_comparendos = _count_label(text, ("comparendos", "comparendo"))
    labeled_multas = _count_paren_or_label(text, ("Total multas", "multas", "multa"))

    empty_markers = (
        "no tiene comparendos",
        "no posee comparendos",
        "sin comparendos",
        "no registra obligaciones",
        "no tiene obligaciones",
        "paz y salvo",
        "no se encontraron resultados",
        "no se encontraron registros",
    )
    explicitly_empty = any(marker in normalized for marker in empty_markers) and not merged

    has_rows = len(merged) > 0
    has_amount = total > 0
    has_labeled = (labeled_comparendos + labeled_multas) > 0
    has_fines = (has_rows or has_amount or has_labeled) and not explicitly_empty

    if has_fines and not has_rows and not has_amount and labeled_multas == 0 and labeled_comparendos == 0:
        # "Total multas ( 0 )" alone is not a hit.
        has_fines = False

    if has_rows:
        comparendos = max(labeled_comparendos, len(merged))
        multas = max(labeled_multas, len(merged))
    else:
        comparendos = labeled_comparendos
        multas = labeled_multas

    if has_fines:
        mensaje = (
            "El ciudadano presenta registros en el portal de Manizales "
            "(pueden estar en audiencia o sin valor liquidado)."
        )
    else:
        mensaje = "El ciudadano no presenta pendientes en el portal de Manizales."

    return {
        "resumen": {
            "comparendos": comparendos if has_fines else 0,
            "multas": multas if has_fines else 0,
            "total": total,
        },
        "tieneMultas": has_fines,
        "mensaje": mensaje,
        "detalles": merged,
    }


def local_manizales_multas(payload: SimitMultasRequest) -> SimitMultasResponse:
    normalized = _normalize_query(payload.documento)
    digits = "".join(char for char in normalized if char.isdigit())
    checksum = sum(int(char) for char in digits) if digits else 0
    has_pending = checksum % 5 == 0 and checksum != 0
    detalles: list[dict[str, object]] = []
    if has_pending:
        detalles = [
            {
                "placa": "ABC123",
                "codigo": "D04",
                "infraccion": "D04 No detenerse ante luz roja o amarilla de semaforo",
                "fecha": "martes 19 de mayo 2026",
                "tipo": "fotodeteccion",
                "estado": "Audiencia",
                "valor": "No aplica",
            }
        ]
    return SimitMultasResponse(
        documentoTail=normalized[-4:] if normalized else "",
        tieneMultas=has_pending,
        resumen={
            "comparendos": 1 if has_pending else 0,
            "multas": 1 if has_pending else 0,
            "total": 0 if has_pending else 0,
        },
        mensaje="Consulta Manizales normalizada sin proveedor externo activo.",
        detalles=detalles,
    )


def _infer_details_from_text(text: str) -> list[dict[str, object]]:
    details: list[dict[str, object]] = []
    # Prefer line-oriented extraction around infraction codes.
    lines = [line.strip() for line in (text or "").splitlines() if line.strip()]
    for index, line in enumerate(lines):
        code_match = INFRACTION_CODE_RE.search(line)
        if not code_match:
            continue
        codigo = code_match.group(1).upper()
        window = " ".join(lines[max(0, index - 2) : min(len(lines), index + 4)])
        plate_match = PLATE_RE.search(window)
        status_match = STATUS_RE.search(window)
        details.append(
            {
                "placa": plate_match.group(1).upper() if plate_match else None,
                "codigo": codigo,
                "infraccion": _clean_infraccion(line, codigo=codigo),
                "fecha": _extract_fecha(window),
                "tipo": _extract_tipo(window),
                "estado": status_match.group(1) if status_match else None,
                "valor": _nearby_valor(window),
            }
        )
    return details


def _nearby_valor(window: str) -> str | None:
    if re.search(r"no\s+aplica", window, flags=re.IGNORECASE):
        return "No aplica"
    money = re.search(r"\$?\s*([\d]{1,3}(?:[.\s]\d{3})+|\d+)\b", window)
    if money:
        return money.group(0).strip()
    return None


def _extract_fecha(text: str) -> str | None:
    match = DATE_RE.search(text or "")
    if not match:
        return None
    return match.group(0).strip()


def _extract_tipo(text: str) -> str | None:
    folded = _fold(text)
    if "FOTODETECCION" in folded or "FOTODETECCI" in folded:
        return "fotodeteccion"
    return None


def _clean_infraccion(raw: str | None, *, codigo: str | None = None) -> str | None:
    if not raw:
        return None
    text = str(raw).strip()
    if not text:
        return None

    lines = [line.strip() for line in text.splitlines() if line.strip()]
    lines = [line for line in lines if _fold(line) not in HEADER_LABELS]
    if not lines:
        return None

    chosen: str | None = None
    for index, candidate in enumerate(lines):
        has_code = bool(codigo and codigo.upper() in candidate.upper()) or bool(INFRACTION_CODE_RE.search(candidate))
        if not has_code:
            continue
        code_token = (codigo or "").upper()
        code_only = bool(
            code_token
            and re.fullmatch(rf"{re.escape(code_token)}\b\.?", candidate, flags=re.IGNORECASE)
        )
        if code_only or len(candidate) <= max(len(code_token) + 2, 4):
            parts = [candidate]
            for nxt in lines[index + 1 : index + 4]:
                folded = _fold(nxt)
                if DATE_RE.search(nxt) or STATUS_RE.search(nxt) or folded in HEADER_LABELS:
                    break
                if PLATE_RE.fullmatch(nxt or ""):
                    break
                if "*" in nxt or folded.startswith("S*****"):
                    break
                if folded.startswith("DETALLE"):
                    break
                parts.append(nxt)
            chosen = " ".join(parts)
        else:
            chosen = candidate
        break

    if chosen is None:
        chosen = lines[0]

    text = chosen
    date_match = DATE_RE.search(text)
    if date_match:
        text = text[: date_match.start()].strip(" -\t")

    text = re.sub(r"\s+", " ", text).strip(" .")
    if not text or _fold(text) in HEADER_LABELS:
        return None
    if len(text) > 140:
        text = text[:137].rstrip() + "..."
    return text


def _merge_details(
    primary: list[dict[str, object]],
    secondary: list[dict[str, object]],
) -> list[dict[str, object]]:
    if primary:
        enriched: list[dict[str, object]] = []
        for row in primary:
            item = dict(row)
            blob = " ".join(str(value) for value in item.values() if value)
            folded = _fold(blob)
            if "ESTADO DE CUENTA" in folded and not INFRACTION_CODE_RE.search(blob):
                continue

            codigo = _first_str(item, ("codigo",)) or _match_group(INFRACTION_CODE_RE, blob)
            if isinstance(codigo, str):
                codigo = codigo.upper()

            placa = _first_str(item, ("placa", "Placa o documento", "col_0"))
            if placa:
                plate_match = PLATE_RE.search(placa)
                placa = plate_match.group(1).upper() if plate_match else None
            if not placa:
                plate_match = PLATE_RE.search(blob)
                placa = plate_match.group(1).upper() if plate_match else None

            infraccion = _clean_infraccion(
                _first_str(
                    item,
                    ("infraccion", "Infracción", "Infraccion", "Descripcion", "Descripción", "col_1"),
                ),
                codigo=codigo,
            )
            candidates: list[str] = []
            if infraccion:
                candidates.append(infraccion)
            for value in item.values():
                cleaned = _clean_infraccion(str(value or ""), codigo=codigo)
                if cleaned:
                    candidates.append(cleaned)
            blob_cleaned = _clean_infraccion(blob, codigo=codigo)
            if blob_cleaned:
                candidates.append(blob_cleaned)
            infraccion = _pick_infraccion(candidates, codigo=codigo)
            if (not infraccion or (codigo and infraccion.upper() == codigo.upper())) and secondary:
                for inferred in secondary:
                    if not isinstance(inferred, dict):
                        continue
                    if codigo and str(inferred.get("codigo") or "").upper() != codigo:
                        continue
                    inferred_text = _clean_infraccion(str(inferred.get("infraccion") or ""), codigo=codigo)
                    if inferred_text and (not codigo or len(inferred_text) > len(codigo) + 3):
                        infraccion = inferred_text
                        break

            fecha = _first_str(item, ("fecha", "Fecha")) or _extract_fecha(blob)
            tipo = _first_str(item, ("tipo",)) or _extract_tipo(blob)

            estado = None
            if "AUDIENCIA" in folded:
                estado = "Audiencia"
            else:
                for key in ("Estado", "estado", "col_2"):
                    cell = str(item.get(key) or "").strip()
                    if not cell or len(cell) > 40:
                        continue
                    status_match = STATUS_RE.search(cell)
                    if status_match:
                        estado = status_match.group(1)
                        break
            if not estado:
                status_match = STATUS_RE.search(blob)
                if status_match:
                    estado = status_match.group(1)

            valor = _first_str(
                item,
                ("valor", "Valor multa", "Total a pagar", "col_3", "col_5"),
            )
            if valor and re.search(r"no\s+aplica", valor, flags=re.IGNORECASE):
                valor = "No aplica"
            elif valor and len(valor) > 40:
                valor = valor.splitlines()[0].strip()[:40]

            if codigo or placa or (estado and infraccion):
                enriched.append(
                    {
                        "placa": placa,
                        "codigo": codigo,
                        "infraccion": infraccion,
                        "fecha": fecha,
                        "tipo": tipo,
                        "estado": estado,
                        "valor": valor,
                    }
                )
        if enriched:
            return enriched
    return secondary


def _pick_infraccion(candidates: list[str], *, codigo: str | None) -> str | None:
    cleaned = []
    for value in candidates:
        text = _clean_infraccion(value, codigo=codigo)
        if text:
            cleaned.append(text)
    if not cleaned:
        return None
    if codigo:
        with_code = [text for text in cleaned if codigo.upper() in text.upper()]
        rich = [text for text in with_code if len(text) > len(codigo) + 3]
        if rich:
            return max(rich, key=len)
        if with_code:
            return max(with_code, key=len)
    return max(cleaned, key=len)


def _first_str(item: dict[str, object], keys: tuple[str, ...]) -> str | None:
    for key in keys:
        value = item.get(key)
        if value is None:
            continue
        text = str(value).strip()
        if text:
            return text
    return None


def _match_group(pattern: re.Pattern[str], text: str) -> str | None:
    match = pattern.search(text or "")
    return match.group(1).upper() if match else None


async def _dismiss_overlays(page: Any) -> None:
    for selector in (
        "button.close",
        ".modal .close",
        "button:has-text('Aceptar')",
        "button:has-text('Cerrar')",
        "[aria-label='Close']",
    ):
        try:
            locator = page.locator(selector).first
            if await locator.count() and await locator.is_visible():
                await locator.click(timeout=1000)
        except Exception:
            continue


async def _fill_search(page: Any, documento: str) -> bool:
    # Home search is Angular (#busqueda). Prefer prototype value setter + nearby button.
    filled = await page.evaluate(
        """
        (query) => {
          const nodes = Array.from(document.querySelectorAll('#busqueda'));
          const input = nodes.find((node) => node && !node.disabled && node.offsetParent)
            || nodes.find((node) => node && !node.disabled)
            || document.querySelector('input[placeholder*="identific" i], input[placeholder*="placa" i]');
          if (!input) return {ok: false};
          input.scrollIntoView({block: 'center'});
          input.focus();
          const setter = Object.getOwnPropertyDescriptor(window.HTMLInputElement.prototype, 'value').set;
          setter.call(input, query);
          input.dispatchEvent(new Event('input', {bubbles: true}));
          input.dispatchEvent(new Event('change', {bubbles: true}));
          const root = input.closest('.input-group, form, .form-group, div') || input.parentElement;
          const btn = root && root.querySelector(
            'button, a.btn, [ng-click], .fa-search, .bi-search, .icon-search, span.input-group-text'
          );
          if (btn) {
            btn.click();
            return {ok: true, via: 'button', value: input.value};
          }
          input.dispatchEvent(new KeyboardEvent('keydown', {key: 'Enter', code: 'Enter', keyCode: 13, which: 13, bubbles: true}));
          input.dispatchEvent(new KeyboardEvent('keyup', {key: 'Enter', code: 'Enter', keyCode: 13, which: 13, bubbles: true}));
          return {ok: true, via: 'enter', value: input.value};
        }
        """,
        documento,
    )
    if isinstance(filled, dict) and filled.get("ok"):
        await page.wait_for_timeout(1200)
        if "resultado-home-public" not in (page.url or ""):
            target = (
                "https://www.movilidadmanizales.com.co/portal-servicios/"
                f"#/resultado-home-public//{documento}/0/"
            )
            try:
                await page.goto(target, wait_until="domcontentloaded", timeout=20000)
            except Exception:
                pass
        return True
    return False


async def _wait_for_results(page: Any, *, timeout_ms: int) -> None:
    deadline = asyncio.get_running_loop().time() + (timeout_ms / 1000)
    while asyncio.get_running_loop().time() < deadline:
        state = await page.evaluate(
            """
            () => {
                const body = (document.body.innerText || '').toLowerCase();
                const url = location.href || '';
                const hasResultRoute = url.includes('resultado-home-public') || url.includes('consultar-multas');
                const hasTable = document.querySelectorAll('table tbody tr, table tr').length > 1;
                const hasCode = /\\b[a-e]\\d{2}\\b/i.test(body);
                const hasSummary = body.includes('total multas') || body.includes('estado de cuenta');
                const empty = body.includes('no se encontraron')
                  || body.includes('paz y salvo')
                  || body.includes('realizar otra consulta');
                return {ready: hasResultRoute || hasTable || hasCode || hasSummary || empty};
            }
            """
        )
        if state.get("ready"):
            await page.wait_for_timeout(700)
            return
        await page.wait_for_timeout(250)


async def _extract_tables(page: Any) -> list[dict[str, object]]:
    tables = await page.evaluate(
        """
        () => {
            const output = [];
            document.querySelectorAll('table').forEach(table => {
                const headerCells = table.querySelectorAll('thead th, thead td, tr:first-child th');
                let headers = Array.from(headerCells).map(th => th.innerText.trim());
                const bodyRows = table.querySelectorAll('tbody tr');
                const rows = bodyRows.length ? bodyRows : table.querySelectorAll('tr');
                rows.forEach(tr => {
                    if (tr.querySelector('th') && !tr.querySelector('td')) return;
                    const cols = Array.from(tr.querySelectorAll('td')).map(td => td.innerText.trim());
                    if (!cols.length) return;
                    const blob = cols.join(' ').toLowerCase();
                    if (blob.includes('total multas') || blob.includes('tarifas adicionales')) return;
                    if (blob.includes('estado de cuenta por infracciones')) return;
                    if (headers.length === cols.length && headers.some(Boolean)) {
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


def _count_label(text: str, labels: tuple[str, ...]) -> int:
    for label in labels:
        match = re.search(rf"{re.escape(label)}\s*[:=]?\s*(\d+)", text, flags=re.IGNORECASE)
        if match:
            return int(match.group(1))
    return 0


def _count_paren_or_label(text: str, labels: tuple[str, ...]) -> int:
    for label in labels:
        match = re.search(rf"{re.escape(label)}\s*\(\s*(\d+)\s*\)", text, flags=re.IGNORECASE)
        if match:
            return int(match.group(1))
        match = re.search(rf"{re.escape(label)}\s*[:=]?\s*(\d+)", text, flags=re.IGNORECASE)
        if match:
            return int(match.group(1))
    return 0


def _extract_payable_total(text: str) -> int:
    # Prefer "Total a pagar" / "COP N" near total multas, ignore "No aplica".
    patterns = (
        r"Total\s+a\s+pagar\s*[:=]?\s*(?:COP\s*)?\$?\s*([\d\.,]+)",
        r"Total\s+multas\s*\(\s*\d+\s*\)\s*(?:COP\s*)?\$?\s*([\d\.,]+)",
        r"(?:Total|Valor|Saldo)\s*[:=]?\s*(?:COP\s*)?\$?\s*([\d\.,]+)",
    )
    for pattern in patterns:
        match = re.search(pattern, text, flags=re.IGNORECASE)
        if not match:
            continue
        amount = _money_value(match.group(1))
        if amount >= 0:
            return amount
    return 0


def _normalize_query(value: str) -> str:
    # Portal accepts document or plate; keep alphanumerics only.
    return "".join(char for char in (value or "").strip().upper() if char.isalnum())


def _money_value(value: Any) -> int:
    digits = re.sub(r"[^\d]", "", str(value or "0"))
    return int(digits) if digits else 0


def _fold(value: str) -> str:
    import unicodedata

    decomposed = unicodedata.normalize("NFKD", value or "")
    ascii_text = "".join(char for char in decomposed if not unicodedata.combining(char))
    return ascii_text.upper()


def _load_async_playwright() -> Any:
    try:
        from playwright.async_api import async_playwright
    except ImportError as exc:
        raise RuntimeError("playwright is required for MANIZALES_PROVIDER_MODE=browser") from exc
    return async_playwright


def _float_env(name: str, *, default: float) -> float:
    raw = os.getenv(name, "").strip()
    try:
        value = float(raw)
    except ValueError:
        return default
    return value if value > 0 else default


def _bool_env(name: str, *, default: bool) -> bool:
    raw = os.getenv(name, "").strip().lower()
    if not raw:
        return default
    return raw in {"1", "true", "yes", "on"}
