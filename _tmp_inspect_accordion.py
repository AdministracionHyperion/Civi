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
        for _ in range(5):
            captcha = await solve(page, CAPTCHA_KEY)
            if len(captcha) < 3:
                continue
            await set_input(page, "input[formcontrolname='captcha']", captcha)
            await page.locator("button.mat-accent, button[type='submit']").first.click()
            await page.wait_for_timeout(5000)
            if "estado de la persona" in (await page.locator("body").inner_text()).lower():
                break
            await page.locator("img.img-fluid[src^='data:image']").first.click()
            await page.wait_for_timeout(800)

        structure = await page.evaluate(
            """
            () => {
              const folded = v => (v || '').normalize('NFD').replace(/[\\u0300-\\u036f]/g, '').toLowerCase();
              const nodes = [];
              for (const el of Array.from(document.querySelectorAll('*'))) {
                const own = (el.childNodes && Array.from(el.childNodes).filter(n => n.nodeType === 3).map(n => n.textContent.trim()).join(' ')) || '';
                const text = (el.innerText || '').trim();
                if (!/licencia/i.test(text) && !/licencia/i.test(own)) continue;
                if (text.length > 120) continue;
                nodes.push({
                  tag: el.tagName,
                  className: (el.className || '').toString().slice(0, 120),
                  role: el.getAttribute('role'),
                  text: text.slice(0, 120),
                  own: own.slice(0, 80)
                });
                if (nodes.length >= 30) break;
              }
              return {
                expansionPanels: document.querySelectorAll('mat-expansion-panel').length,
                accordion: document.querySelectorAll('mat-accordion').length,
                nodes
              };
            }
            """
        )
        print(json.dumps(structure, ensure_ascii=False, indent=2))

        # Try Playwright locator click on exact text
        loc = page.get_by_text("Licencia(s) de conducción", exact=False).first
        try:
            await loc.click(timeout=5000)
            clicked_via = "get_by_text"
        except Exception as exc:
            clicked_via = f"fail:{type(exc).__name__}"
        await page.wait_for_timeout(2500)
        body = await page.locator("body").inner_text()
        print(
            json.dumps(
                {
                    "clicked_via": clicked_via,
                    "hasVerDetalle": "ver detalle" in body.lower(),
                    "detailCount": await page.locator("text=Ver Detalle").count(),
                    "bodyLen": len(body),
                },
                ensure_ascii=False,
                indent=2,
            )
        )
        await browser.close()


if __name__ == "__main__":
    asyncio.run(main())
