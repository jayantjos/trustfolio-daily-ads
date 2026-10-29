#!/usr/bin/env python3
"""Read-only single Flipkart POCO PDP Chromium test; no MongoDB writes or API keys."""
import asyncio, json, re, time
from pathlib import Path
from playwright.async_api import async_playwright

URL="https://www.flipkart.com/poco-x8-pro-max-blue-512-gb/p/itmfc8cc712fe4a5?pid=MOBHH2KYWG8UBBAF"
CHROME=str(Path.home()/".cache/ms-playwright/chromium-1248/chrome-linux64/chrome")
async def main():
    start=time.monotonic()
    async with async_playwright() as p:
        browser=await p.chromium.launch(
            executable_path=CHROME,headless=True,
            args=["--no-sandbox","--disable-dev-shm-usage"]
        )
        context=await browser.new_context(locale="en-IN",timezone_id="Asia/Kolkata",viewport={"width":1380,"height":860})
        page=await context.new_page()
        observed=[]
        async def response_handler(resp):
            if "flipkart.com" not in resp.url:return
            if len(observed)>=80:return
            try:
                typ=resp.headers.get("content-type","")
                if "json" in typ or "product" in resp.url or "price" in resp.url:
                    from urllib.parse import urlsplit
                    u=urlsplit(resp.url)
                    observed.append({"path":u.path[:110],"code":resp.status,"type":typ[:50]})
            except Exception:pass
        page.on("response",response_handler)
        try:
            result=await page.goto(URL,wait_until="domcontentloaded",timeout=24000)
            await page.wait_for_timeout(6500)
            title=await page.title()
            body=(await page.locator("body").inner_text(timeout=3000))[:22000]
            hit=[]
            for marker in ["POCO X8 Pro Max","Selected Color","Variant:","₹49,999","₹50,999","₹52,999","₹54,999","Out of stock","Buy now"]:
                hit.append({marker:marker in body})
            snippets=[]
            for m in re.finditer(r"(?:₹|Rs\.?)\s*[\d,]{3,}",body):
                context_text=body[max(0,m.start()-75):min(len(body),m.end()+80)].replace("\n"," ")
                snippets.append(context_text)
                if len(snippets)>=10:break
            print("PLAYWRIGHT_PDP_RESULT="+json.dumps({
                "navigation_http":result.status if result else None,
                "title":title[:200],"url_path":page.url.split("?")[0],
                "body_chars":len(body),
                "markers":hit,
                "price_snippets":snippets,
                "api_responses":observed[:20],
                "elapsed_ms":round(1000*(time.monotonic()-start))
            }))
        finally:
            await context.close();await browser.close()
    print("READ_ONLY_BROWSING=YES")
if __name__=="__main__":
    try:asyncio.run(main())
    except Exception as exc:
        print("PLAYWRIGHT_ERROR="+type(exc).__name__+":"+str(exc)[:230])
        raise
