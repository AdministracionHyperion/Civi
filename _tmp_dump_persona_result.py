import asyncio
import json
import os
from playwright.async_api import async_playwright

URL = "https://portalpublico.runt.gov.co/#/consulta-ciudadano-documento/consulta/consulta-ciudadano-documento"
DOC = os.getenv("DOC", "1052838811")
CAPTCHA_KEY = os.getenv("CAPTCHA_API_KEY", "")


async def solve(page, api_key: str) -> str:
    import base64
    import re
    import httpx

    img = page.locator("img.img-fluid[src^='data:image'], img.img-captcha").first
    raw = await img.screenshot()
    if api_key:
        async with httpx.AsyncClient(timeout=45) as client:
            created = await client.post(
                "https://api.anti-captcha.com/createTask",
                json={
                    "clientKey": api_key,
                    "task": {"type": "ImageToTextTask", "body": base64.b64encode(raw).decode(), "case": True},
                },
            )
            task_id = created.json().get("taskId")
            for _ in range(20):
                await asyncio.sleep(1.5)
                result = await client.post(
                    "https://api.anti-captcha.com/getTaskResult",
                    json={"clientKey": api_key, "taskId": task_id},
                )
                data = result.json()
                if data.get("status") == "ready":
                    return re.sub(r"[^A-Za-z0-9]", "", str((data.get("solution") or {}).get("text") or ""))
    from ddddocr import DdddOcr

    return re.sub(r"[^A-Za-z0-9]", "", str(DdddOcr(show_ad=False).classification(raw) or ""))


async def set_input(page, selector: str, value: str) -> None:
    await page.eval_on_selector(
        selector,
        """(el, value) => {
            el.value = value;
            el.dispatchEvent(new Event('input', {bubbles:true}));
            el.dispatchEvent(new Event('change', {bubbles:true}));
        }""",
        value,
    )


async def main() -> None:
    async with async_playwright() as p:
        browser = await p.chromium.launch(headless=True, args=["--no-sandbox", "--disable-dev-shm-usage"])
        page = await browser.new_page(viewport={"width": 1366, "height": 768})
        await page.goto(URL, wait_until="domcontentloaded", timeout=90000)
        await page.locator("input[formcontrolname='documento']").wait_for(timeout=90000)
        await set_input(page, "input[formcontrolname='documento']", DOC)
        ok = False
        for attempt in range(5):
            captcha = await solve(page, CAPTCHA_KEY)
            if len(captcha) < 3:
                await page.locator("img.img-fluid[src^='data:image']").first.click()
                await page.wait_for_timeout(1000)
                continue
            await set_input(page, "input[formcontrolname='captcha']", captcha)
            await page.locator("button.mat-accent, button[type='submit']").first.click()
            await page.wait_for_timeout(5000)
            body = (await page.locator("body").inner_text()).lower()
            if "captcha" in body and ("incorrecto" in body or "invalido" in body or "inválido" in body):
                await page.locator("img.img-fluid[src^='data:image']").first.click()
                await page.wait_for_timeout(1000)
                continue
            if "estado de la persona" in body or "nombre completo" in body:
                ok = True
                break
        if not ok:
            print(json.dumps({"error": "consult_failed"}))
            await browser.close()
            return

        await page.wait_for_timeout(8000)
        await page.evaluate("window.scrollTo(0, document.body.scrollHeight)")
        await page.wait_for_timeout(2000)

        dump = await page.evaluate(
            """
            () => {
              const text = (document.body.innerText || '');
              const panels = Array.from(document.querySelectorAll('mat-expansion-panel, mat-tab, .mat-tab-label, button, a'))
                .map(el => (el.innerText || '').trim().slice(0, 80))
                .filter(t => t && t.length < 80)
                .slice(0, 40);
              const tables = Array.from(document.querySelectorAll('table, mat-table')).map((t, i) => ({
                i,
                tag: t.tagName,
                className: t.className,
                text: (t.innerText || '').slice(0, 400),
                rows: t.querySelectorAll('tr, mat-row').length
              }));
              return {
                url: location.href,
                bodyLen: text.length,
                bodyPreview: text.slice(0, 1200),
                panels,
                tables
              };
            }
            """
        )
        print(json.dumps(dump, ensure_ascii=False, indent=2))
        await browser.close()


if __name__ == "__main__":
    asyncio.run(main())
