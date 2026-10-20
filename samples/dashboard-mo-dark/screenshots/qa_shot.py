# -*- coding: utf-8 -*-
"""QA 截图脚本：1280x800 桌面 / 390x844 移动双视口，检查 console 报错与 404。"""
import pathlib
from patchright.sync_api import sync_playwright

BASE = pathlib.Path(__file__).resolve().parent.parent
URL = (BASE / "index.html").as_uri()
OUT = BASE / "screenshots"


def run(viewport, name):
    errors, failed_req = [], []
    with sync_playwright() as p:
        browser = p.chromium.launch(headless=True)
        page = browser.new_page(viewport={"width": viewport[0], "height": viewport[1]})
        page.on("console", lambda m: errors.append(m.text) if m.type == "error" else None)
        page.on("pageerror", lambda e: errors.append(str(e)))
        page.on("requestfailed", lambda r: failed_req.append(r.url))
        page.on("response", lambda r: failed_req.append(f"{r.status} {r.url}") if r.status >= 400 else None)
        page.goto(URL, wait_until="networkidle")
        page.wait_for_timeout(400)

        # 横向溢出测量
        sw = page.evaluate("document.documentElement.scrollWidth")
        cw = page.evaluate("document.documentElement.clientWidth")
        page.screenshot(path=str(OUT / name), full_page=True)
        browser.close()
    return sw, cw, errors, failed_req


for viewport, name in [((1280, 800), "qa-desktop.png"), ((390, 844), "qa-mobile.png")]:
    sw, cw, errs, reqs = run(viewport, name)
    print(f"[{name}] viewport={viewport} scrollWidth={sw} clientWidth={cw} overflow={sw > cw}")
    print(f"  console_errors={errs}")
    print(f"  failed_or_404={reqs}")
