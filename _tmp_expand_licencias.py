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
        for _ in range(5):
            captcha = await solve(page, CAPTCHA_KEY)
            if len(captcha) < 3:
                continue
            await set_input(page, "input[formcontrolname='captcha']", captcha)
            await page.locator("button.mat-accent, button[type='submit']").first.click()
            await page.wait_for_timeout(5000)
            body = (await page.locator("body").inner_text()).lower()
            if "estado de la persona" in body:
                ok = True
                break
            await page.locator("img.img-fluid[src^='data:image']").first.click()
            await page.wait_for_timeout(800)
        if not ok:
            print(json.dumps({"error": "consult_failed"}))
            await browser.close()
            return

        clicked = await page.evaluate(
            """
            () => {
              const folded = v => (v || '').normalize('NFD').replace(/[\\u0300-\\u036f]/g, '').toLowerCase();
              const marker = 'licencia(s) de conduccion';
              const all = Array.from(document.querySelectorAll('mat-expansion-panel-header, .mat-expansion-panel-header, button, a, div[role="button"], mat-panel-title, div, span'));
              for (const el of all) {
                const text = folded(el.innerText || el.textContent || '');
                if (text.includes(marker) || text.includes('licencias de conduccion')) {
                  const clickable = el.closest('mat-expansion-panel-header, .mat-expansion-panel-header, button, a, div[role="button"]') || el;
                  clickable.click();
                  return (el.innerText || '').trim().slice(0, 80);
                }
              }
              return null;
            }
            """
        )
        await page.wait_for_timeout(2500)
        body = await page.locator("body").inner_text()
        detail_count = await page.locator("a:has-text('Ver Detalle'), span:has-text('Ver Detalle'), td:has-text('Ver Detalle')").count()
        print(
            json.dumps(
                {
                    "clicked": clicked,
                    "hasVerDetalle": "ver detalle" in body.lower(),
                    "hasNroLicencia": "nro licencia" in body.lower() or "nro. licencia" in body.lower(),
                    "detailCount": detail_count,
                    "bodyLen": len(body),
                    "snippet": body[body.lower().find("licencia") : body.lower().find("licencia") + 500]
                    if "licencia" in body.lower()
                    else body[-500:],
                },
                ensure_ascii=False,
                indent=2,
            )
        )
        await browser.close()


if __name__ == "__main__":
    asyncio.run(main())
