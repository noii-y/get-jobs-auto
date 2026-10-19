# -*- coding: utf-8 -*-
"""
登录中心扫码登录 —— patchright 可行性验证 spike（隔离实验，非主应用代码）

设计目标：用最小成本验证「patchright 持久化 context + storage_state」能否支撑
Boss 直聘扫码登录链路，不绕过任何风控/验证码/滑块，真实扫码留给真人。

子命令：
  fingerprint   打印反检测指纹（navigator.webdriver / window.chrome / WebGL 等），写 JSON
  public-test   公开站点(example.com) localStorage + storage_state 存取闭环自测
  open-login    打开 Boss 登录页（可见浏览器），截图二维码/登录入口后自动关闭
  wait-login    打开 Boss 登录页等待真人扫码，自动检测登录成功信号，保存 storage_state
  verify-state  用已保存的 storage_state 在全新 context 中重开 Boss，校验是否仍免登录

所有命令都带超时，绝不无限挂起；用完即关浏览器进程。
"""

import argparse
import json
import sys
import time
from pathlib import Path

# ---------------------------------------------------------------------------
# 路径常量：全部落在本 spike 目录内，绝不指向用户日常 Chrome
# ---------------------------------------------------------------------------
BASE_DIR = Path(__file__).resolve().parent
PROFILES_DIR = BASE_DIR / "profiles"
BOSS_PROFILE_DIR = PROFILES_DIR / "boss"          # 持久化 user_data_dir
STATE_DIR = BASE_DIR / "state"
SCREENSHOTS_DIR = BASE_DIR / "screenshots"
FINGERPRINT_FILE = BASE_DIR / "state" / "fingerprint.json"
BOSS_STATE_FILE = STATE_DIR / "boss_storage_state.json"

# Boss 直聘登录入口（最终以实际页面为准；open-login 会记录真实落地 URL）
BOSS_HOME_URL = "https://www.zhipin.com/"
BOSS_LOGIN_URL = "https://www.zhipin.com/web/user/?ka=header-login"

# 判定"已离开登录页"的 URL 特征
LOGIN_URL_HINTS = ("/web/user", "ka=header-login", "/user/?")

for _d in (PROFILES_DIR, BOSS_PROFILE_DIR, STATE_DIR, SCREENSHOTS_DIR):
    _d.mkdir(parents=True, exist_ok=True)


# ---------------------------------------------------------------------------
# 反检测指纹采集（在页面上下文里求值）
# ---------------------------------------------------------------------------
FINGERPRINT_JS = r"""
() => {
  function webglInfo() {
    try {
      const gl = document.createElement('canvas').getContext('webgl');
      if (!gl) return {vendor: 'no-webgl', renderer: 'no-webgl'};
      const ext = gl.getExtension('WEBGL_debug_renderer_info');
      if (!ext) return {vendor: 'webgl-ok-no-ext', renderer: 'webgl-ok-no-ext'};
      return {
        vendor: String(gl.getParameter(ext.UNMASKED_VENDOR_WEBGL)),
        renderer: String(gl.getParameter(ext.UNMASKED_RENDERER_WEBGL)),
      };
    } catch (e) { return {vendor: 'err:' + e, renderer: 'err:' + e}; }
  }
  const w = webglInfo();
  return {
    'navigator.webdriver': navigator.webdriver,
    'window.chrome_exists': (typeof window.chrome !== 'undefined'),
    'window.chrome.runtime_exists': !!(window.chrome && window.chrome.runtime),
    'navigator.plugins.length': navigator.plugins ? navigator.plugins.length : -1,
    'navigator.plugins.names': Array.from(navigator.plugins || []).map(p => p.name),
    'navigator.userAgent': navigator.userAgent,
    'navigator.languages': Array.from(navigator.languages || []),
    'navigator.platform': navigator.platform,
    'navigator.hardwareConcurrency': navigator.hardwareConcurrency,
    'navigator.deviceMemory': navigator.deviceMemory,
    'screen': (window.screen ? (window.screen.width + 'x' + window.screen.height + '@' + window.screen.devicePixelRatio) : 'n/a'),
    'webgl.vendor': w.vendor,
    'webgl.renderer': w.renderer,
  };
}
"""


def _cookie_names(context):
    """只取 cookie 名字（绝不返回值），用于观察登录态变化。"""
    try:
        return sorted({c.get("name", "") for c in context.cookies()})
    except Exception as e:  # pragma: no cover
        return ["<err:%s>" % e]


def _is_login_url(url: str) -> bool:
    return any(h in url for h in LOGIN_URL_HINTS)


# ---------------------------------------------------------------------------
# 子命令：fingerprint
# ---------------------------------------------------------------------------
def cmd_fingerprint(args):
    from patchright.sync_api import sync_playwright

    print("[fingerprint] 启动持久化 context，采集反检测指纹 ...")
    with sync_playwright() as p:
        ctx = p.chromium.launch_persistent_context(
            str(BOSS_PROFILE_DIR),
            headless=False,
            viewport={"width": 1280, "height": 800},
        )
        page = ctx.pages[0] if ctx.pages else ctx.new_page()
        page.goto("https://example.com/", wait_until="domcontentloaded", timeout=60000)
        time.sleep(1.5)  # 等 JS 环境稳定
        fp = page.evaluate(FINGERPRINT_JS)
        fp["_captured_at"] = time.strftime("%Y-%m-%d %H:%M:%S")
        FINGERPRINT_FILE.parent.mkdir(parents=True, exist_ok=True)
        FINGERPRINT_FILE.write_text(json.dumps(fp, ensure_ascii=False, indent=2), encoding="utf-8")
        print(json.dumps(fp, ensure_ascii=False, indent=2))
        print("[fingerprint] 已保存 ->", FINGERPRINT_FILE)
        ctx.close()
    print("[fingerprint] 完成（浏览器已关闭）。")


# ---------------------------------------------------------------------------
# 子命令：public-test  公开站点 localStorage 持久化闭环
# ---------------------------------------------------------------------------
def cmd_public_test(args):
    """
    证明 storage_state 存取机制正确：
      1) 持久化 context 打开 example.com，写一个 localStorage 标记
      2) storage_state(path) 落盘
      3) 全新非持久化 context，用 storage_state=文件 加载，读回该标记
    注意：localStorage 按 origin 隔离，三步必须都在 https://example.com/ 同一 origin。
    """
    from patchright.sync_api import sync_playwright

    marker_key = "__spike_persist_marker__"
    marker_value = "hello-storage-state-" + time.strftime("%Y%m%d-%H%M%S")
    pub_state = STATE_DIR / "public_storage_state.json"

    print("[public-test] 第1步：写入 localStorage 标记 ...")
    with sync_playwright() as p:
        ctx = p.chromium.launch_persistent_context(
            str(BOSS_PROFILE_DIR),
            headless=True,
            viewport={"width": 1280, "height": 800},
        )
        page = ctx.pages[0] if ctx.pages else ctx.new_page()
        page.goto("https://example.com/", wait_until="domcontentloaded", timeout=60000)
        page.evaluate(
            "([k, v]) => { localStorage.setItem(k, v); }", [marker_key, marker_value]
        )
        saved = page.evaluate("(k) => localStorage.getItem(k)", marker_key)
        print("[public-test] 写入后立即读回:", saved)
        ctx.storage_state(path=str(pub_state))
        print("[public-test] 已落盘 storage_state ->", pub_state)
        ctx.close()

    print("[public-test] 第2步：全新 context 加载 storage_state，校验标记 ...")
    with sync_playwright() as p:
        browser = p.chromium.launch(headless=True)
        new_ctx = browser.new_context(storage_state=str(pub_state))
        page = new_ctx.new_page()
        page.goto("https://example.com/", wait_until="domcontentloaded", timeout=60000)
        time.sleep(0.8)
        readback = page.evaluate("(k) => localStorage.getItem(k)", marker_key)
        print("[public-test] 新 context 读回 localStorage:", readback)
        ok = (readback == marker_value)
        print("[public-test] 闭环结果:", "✅ PASS（持久化存取正确）" if ok else "❌ FAIL")
        new_ctx.close()
        browser.close()
    sys.exit(0 if ok else 1)


# ---------------------------------------------------------------------------
# 子命令：open-login  打开 Boss 登录页并截图
# ---------------------------------------------------------------------------
def cmd_open_login(args):
    from patchright.sync_api import sync_playwright

    shot = SCREENSHOTS_DIR / "boss_login.png"
    print("[open-login] 打开 Boss 登录页（可见浏览器）...")
    with sync_playwright() as p:
        ctx = p.chromium.launch_persistent_context(
            str(BOSS_PROFILE_DIR),
            headless=False,
            viewport={"width": 1280, "height": 860},
        )
        page = ctx.pages[0] if ctx.pages else ctx.new_page()
        page.goto(BOSS_LOGIN_URL, wait_until="domcontentloaded", timeout=60000)
        try:
            page.wait_for_load_state("networkidle", timeout=15000)
        except Exception:
            pass
        time.sleep(2.5)  # 等二维码/登录入口渲染
        print("[open-login] 真实落地 URL:", page.url)
        # 切到「APP扫码登录」标签，让截图直接展示二维码本体（核心流程）
        try:
            page.get_by_text("APP扫码登录", exact=True).first.click(timeout=5000)
            time.sleep(2.0)
            print("[open-login] 已切换到 APP扫码登录 标签")
        except Exception as e:
            print("[open-login] 未能自动切换到扫码标签（保留默认登录视图）:", e)
        page.screenshot(path=str(shot), full_page=False)
        print("[open-login] 截图已保存 ->", shot)
        print("[open-login] 当前 cookie 名（不含值）:", _cookie_names(ctx))
        ctx.close()
    print("[open-login] 完成（浏览器已关闭）。")


# ---------------------------------------------------------------------------
# 子命令：wait-login  等待真人扫码 + 自动检测成功 + 保存 storage_state
# ---------------------------------------------------------------------------
def cmd_wait_login(args):
    from patchright.sync_api import sync_playwright

    timeout_s = args.timeout
    print("[wait-login] 打开 Boss 登录页，请用 Boss 直聘 App 扫码。")
    print("[wait-login] 自动检测登录成功信号；超时 %d 秒后退出。" % timeout_s)

    with sync_playwright() as p:
        ctx = p.chromium.launch_persistent_context(
            str(BOSS_PROFILE_DIR),
            headless=False,
            viewport={"width": 1280, "height": 860},
        )
        page = ctx.pages[0] if ctx.pages else ctx.new_page()
        page.goto(BOSS_LOGIN_URL, wait_until="domcontentloaded", timeout=60000)
        time.sleep(2)

        baseline_cookies = set(_cookie_names(ctx))
        print("[wait-login] 登录前 baseline cookie 名:", sorted(baseline_cookies))

        start = time.time()
        left_login_streak = 0
        logged_in = False
        last_url = page.url

        while time.time() - start < timeout_s:
            time.sleep(2)
            try:
                url = page.url
                names = set(_cookie_names(ctx))
            except Exception:
                continue

            if url != last_url:
                print("[wait-login] URL 变化:", last_url, "->", url)
                last_url = url

            # URL 是否已离开登录路由（仍在 www.zhipin.com 域内）
            left_login = (not _is_login_url(url)) and url.startswith("https://www.zhipin.com/")

            # URL 离开登录路由并稳定停留（并列信号，兜底）
            if left_login:
                left_login_streak += 1
            else:
                left_login_streak = 0

            # 新 cookie（baseline 之外）
            new_cookies = names - baseline_cookies

            # 强信号：核心会话 cookie wt2 新出现 且 URL 已离开登录路由。
            # 为什么是组合而不是单看 wt2：公开资料显示 Boss 的风控 token __zp_stoken__
            # 在未登录页就会被页面 JS 种下；wt2 是否也会在某些未登录页面被预先种下并不确定，
            # 因此要求「wt2 不在 baseline（=登录后才下发）+ URL 确已跳离登录页」双条件，
            # 避免把未登录态误判为已登录。命中即判定，不必再等 URL 连续稳定。
            wt2_strong = ("wt2" in new_cookies) and left_login

            if wt2_strong:
                print("[wait-login] ✅ 强信号命中：新 cookie 含 wt2 且已离开登录路由。")
                print("[wait-login] 本次新出现 cookie 名:", sorted(new_cookies))
                logged_in = True
                break
            if left_login_streak >= 2:  # 并列信号：连续 ~4 秒稳定在登录后页面
                print("[wait-login] 并列信号命中：已离开登录页并稳定停留，新 cookie:", sorted(new_cookies))
                logged_in = True
                break

        if not logged_in:
            print("[wait-login] ⚠ 超时未检测到登录成功。未保存 storage_state。")
            ctx.close()
            sys.exit(2)

        time.sleep(1.5)  # 让最后一波 cookie/localStorage 落定
        final_cookies = _cookie_names(ctx)
        print("[wait-login] 登录后 cookie 名（不含值）:", final_cookies)
        ctx.storage_state(path=str(BOSS_STATE_FILE))
        print("[wait-login] ✅ storage_state 已保存 ->", BOSS_STATE_FILE)
        ctx.close()
    print("[wait-login] 完成（浏览器已关闭）。")


# ---------------------------------------------------------------------------
# 子命令：verify-state  用 storage_state 全新 context 校验免登录
# ---------------------------------------------------------------------------
def cmd_verify_state(args):
    from patchright.sync_api import sync_playwright

    if not BOSS_STATE_FILE.exists():
        print("[verify-state] ❌ 未找到 storage_state 文件:", BOSS_STATE_FILE)
        sys.exit(3)

    print("[verify-state] 用全新 context 加载 storage_state，重开 Boss 首页 ...")
    with sync_playwright() as p:
        browser = p.chromium.launch(headless=True)
        ctx = browser.new_context(storage_state=str(BOSS_STATE_FILE))
        page = ctx.new_page()
        page.goto(BOSS_HOME_URL, wait_until="domcontentloaded", timeout=60000)
        try:
            page.wait_for_load_state("networkidle", timeout=12000)
        except Exception:
            pass
        time.sleep(1.5)
        final_url = page.url
        names = _cookie_names(ctx)
        print("[verify-state] 落地 URL:", final_url)
        print("[verify-state] 携带的 cookie 名（不含值）:", names)

        # 若仍被踢回登录页 → 登录态失效
        if _is_login_url(final_url):
            print("[verify-state] ❌ 落地仍为登录页 => storage_state 登录态已失效。")
            verdict = False
        else:
            print("[verify-state] ✅ 未被重定向到登录页 => storage_state 免登录有效。")
            verdict = True
        shot = SCREENSHOTS_DIR / "verify_state.png"
        page.screenshot(path=str(shot))
        print("[verify-state] 校验截图 ->", shot)
        ctx.close()
        browser.close()
    sys.exit(0 if verdict else 4)


# ---------------------------------------------------------------------------
# CLI
# ---------------------------------------------------------------------------
def main():
    ap = argparse.ArgumentParser(description="Boss 直聘扫码登录 patchright spike")
    sub = ap.add_subparsers(dest="cmd", required=True)

    sub.add_parser("fingerprint", help="打印反检测指纹并保存 JSON")
    sub.add_parser("public-test", help="公开站点 localStorage 持久化闭环自测")
    sub.add_parser("open-login", help="打开 Boss 登录页并截图")
    p_wait = sub.add_parser("wait-login", help="等待真人扫码并自动保存 storage_state")
    p_wait.add_argument("--timeout", type=int, default=180, help="等待扫码超时秒数（默认180）")
    sub.add_parser("verify-state", help="校验已保存的 storage_state 是否仍免登录")

    args = ap.parse_args()
    {
        "fingerprint": cmd_fingerprint,
        "public-test": cmd_public_test,
        "open-login": cmd_open_login,
        "wait-login": cmd_wait_login,
        "verify-state": cmd_verify_state,
    }[args.cmd](args)


if __name__ == "__main__":
    main()
