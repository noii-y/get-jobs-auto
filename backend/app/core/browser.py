"""浏览器管理工具 - 封装DrissionPage的浏览器连接逻辑"""
import os
import sys
import time
import shutil
from pathlib import Path
from typing import Optional, List
from DrissionPage import ChromiumPage, ChromiumOptions
from app.config import settings


def find_chrome_path() -> Optional[str]:
    """跨平台自动查找 Chrome / Edge 可执行文件路径"""
    # 1. 环境变量优先
    env_path = os.environ.get("CHROME_PATH")
    if env_path and Path(env_path).exists():
        return env_path

    # 2. PATH 中查找
    for name in ("google-chrome", "google-chrome-stable", "chrome", "chromium", "chromium-browser"):
        found = shutil.which(name)
        if found:
            return found

    # 3. 平台常见安装路径
    candidates: List[str] = []

    if sys.platform == "win32":
        program_files = os.environ.get("ProgramFiles", r"C:\Program Files")
        program_files_x86 = os.environ.get("ProgramFiles(x86)", r"C:\Program Files (x86)")
        local_app_data = os.environ.get("LOCALAPPDATA", "")
        candidates = [
            os.path.join(program_files, r"Google\Chrome\Application\chrome.exe"),
            os.path.join(program_files_x86, r"Google\Chrome\Application\chrome.exe"),
            os.path.join(local_app_data, r"Google\Chrome\Application\chrome.exe"),
            os.path.join(program_files_x86, r"Microsoft\Edge\Application\msedge.exe"),
            os.path.join(program_files, r"Microsoft\Edge\Application\msedge.exe"),
        ]
    elif sys.platform == "darwin":
        candidates = [
            "/Applications/Google Chrome.app/Contents/MacOS/Google Chrome",
            "/Applications/Chromium.app/Contents/MacOS/Chromium",
            "/Applications/Microsoft Edge.app/Contents/MacOS/Microsoft Edge",
            os.path.expanduser("~/Applications/Google Chrome.app/Contents/MacOS/Google Chrome"),
        ]
    else:  # Linux
        candidates = [
            "/usr/bin/google-chrome",
            "/usr/bin/google-chrome-stable",
            "/usr/bin/chromium",
            "/usr/bin/chromium-browser",
            "/snap/bin/chromium",
            "/opt/google/chrome/chrome",
        ]

    for path in candidates:
        if path and Path(path).exists():
            return path

    return None


class BrowserManager:
    """浏览器管理器，支持接管模式和独立模式"""

    def __init__(self):
        self.page: Optional[ChromiumPage] = None
        self._mode = "attach"  # attach: 接管已打开的浏览器; launch: 独立启动

    def connect(self, mode: str = "attach") -> ChromiumPage:
        """
        连接浏览器
        mode: attach - 接管已打开的Chrome（需要Chrome以--remote-debugging-port=9222启动）
              launch - 独立启动一个浏览器实例
        """
        self._mode = mode

        if mode == "attach":
            # 接管模式：连接到已运行的Chrome
            try:
                co = ChromiumOptions()
                co.set_local_port(settings.chrome_debug_port)
                self.page = ChromiumPage(co)
                print(f"[Browser] 成功接管Chrome浏览器 (端口 {settings.chrome_debug_port})")
                return self.page
            except Exception as e:
                print(f"[Browser] 接管失败: {e}，尝试独立启动模式")
                return self.connect(mode="launch")

        # 独立启动模式
        co = ChromiumOptions()

        # 自动查找浏览器路径
        chrome_path = find_chrome_path()
        if chrome_path:
            co.set_browser_path(chrome_path)
            print(f"[Browser] 使用浏览器: {chrome_path}")
        else:
            print("[Browser] 警告: 未自动找到Chrome/Edge，将使用DrissionPage默认路径")

        # 用户数据目录（独立模式使用单独的profile，不影响用户日常浏览器）
        user_data = str(settings.browser_data_dir / "chrome_profile")
        co.set_user_data_path(user_data)

        if settings.browser_headless:
            co.headless()
        co.set_argument("--disable-blink-features=AutomationControlled")
        co.set_argument("--no-sandbox")
        co.set_argument("--disable-dev-shm-usage")

        self.page = ChromiumPage(co)
        print("[Browser] 独立启动Chrome浏览器成功")
        return self.page

    def get_page(self) -> ChromiumPage:
        """获取当前页面"""
        if self.page is None:
            raise RuntimeError("浏览器未连接，请先调用connect()")
        return self.page

    def goto(self, url: str, wait_complete: bool = True):
        """导航到指定URL"""
        page = self.get_page()
        page.get(url)
        if wait_complete:
            try:
                page.wait.doc_loaded()
            except:
                pass
        time.sleep(1.5)  # 额外等待页面渲染

    def scroll_down(self, times: int = 3, delay: float = 0.8):
        """向下滚动页面"""
        page = self.get_page()
        for _ in range(times):
            page.scroll.down()
            time.sleep(delay)

    def close(self):
        """关闭浏览器（仅独立模式）"""
        if self.page and self._mode == "launch":
            try:
                self.page.quit()
            except:
                pass
        self.page = None

    def __del__(self):
        # 不自动关闭，接管模式下关闭会影响用户浏览器
        pass


# 全局浏览器管理器
browser_manager = BrowserManager()
