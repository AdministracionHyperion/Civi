from __future__ import annotations

import asyncio
import base64
import os
import re
from typing import Any

import httpx

from runt_service.shared.vehicle_analysis import fold

CAPTCHA_CREATE_TASK_URL = "https://api.anti-captcha.com/createTask"
CAPTCHA_RESULT_URL = "https://api.anti-captcha.com/getTaskResult"
CAPTCHA_SELECTOR = (
    "img.img-captcha, img[alt='Captcha'], img[alt*='aptcha' i], "
    "img.img-responsive.img-fluid, img.img-fluid[src^='data:image']"
)
BROWSER_LOCK = asyncio.Semaphore(1)


async def solve_captcha_on_page(
    page: Any,
    *,
    captcha_api_key: str,
    ocr_holder: Any,
) -> str:
    captcha = page.locator(CAPTCHA_SELECTOR).first
    image_bytes = await captcha.screenshot(timeout=10000)

    if captcha_api_key:
        try:
            result = await anti_captcha_solve(image_bytes, captcha_api_key)
            if len(result) >= 3:
                return result
        except Exception:
            pass

    return await ocr_captcha_solve(image_bytes, ocr_holder)


async def anti_captcha_solve(image_bytes: bytes, api_key: str) -> str:
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


async def ocr_captcha_solve(image_bytes: bytes, ocr_holder: Any) -> str:
    try:
        if getattr(ocr_holder, "_ocr", None) is None:
            from ddddocr import DdddOcr

            ocr_holder._ocr = DdddOcr(show_ad=False)
    except ImportError as exc:
        raise RuntimeError("ddddocr is required for OCR captcha fallback") from exc
    result = ocr_holder._ocr.classification(image_bytes) or ""
    return re.sub(r"[^A-Za-z0-9]", "", str(result))


async def refresh_captcha(page: Any, *, captcha_input_selector: str = "#mat-input-2") -> None:
    await page.locator(CAPTCHA_SELECTOR).first.click(timeout=5000)
    await page.wait_for_timeout(1000)
    try:
        await set_input_value(page, captcha_input_selector, "")
    except Exception:
        return


async def select_document_type(page: Any, document_type: str) -> None:
    if not document_type or document_type == "CC":
        return
    try:
        selector = page.locator(
            "mat-select[formcontrolname='tipoDocumento'], mat-select[formcontrolname='tipoDoc'], #mat-select-0, #mat-select-4"
        ).first
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


async def set_input_value(page: Any, selector: str, value: str) -> None:
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


def load_async_playwright() -> Any:
    try:
        from playwright.async_api import async_playwright
    except ImportError as exc:
        raise RuntimeError("playwright is required for RUNT browser provider mode") from exc
    return async_playwright


def float_env(name: str, *, default: float) -> float:
    raw_value = os.getenv(name, "").strip()
    if not raw_value:
        return default
    try:
        return float(raw_value)
    except ValueError:
        return default


def int_env(name: str, *, default: int) -> int:
    raw_value = os.getenv(name, "").strip()
    if not raw_value:
        return default
    try:
        return int(raw_value)
    except ValueError:
        return default


def bool_env(name: str, *, default: bool) -> bool:
    raw_value = os.getenv(name, "").strip().lower()
    if not raw_value:
        return default
    return raw_value in {"1", "true", "yes", "si"}
