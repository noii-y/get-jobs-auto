# -*- coding: utf-8 -*-
"""一键启动脚本（带启动前环境自检与端口自愈）"""
import argparse
import os
import subprocess
import sys
import time
import webbrowser
from pathlib import Path

# 切换到backend目录
backend_dir = Path(__file__).resolve().parent
os.chdir(backend_dir)
sys.path.insert(0, str(backend_dir))

try:
    sys.stdout.reconfigure(encoding="utf-8")
except Exception:
    pass


def _cmdline_of_pid(pid: int):
    """读取进程命令行（Windows WMI/CIM）；任何失败都返回 None。
    判定不精确时调用方不得杀进程。"""
    try:
        r = subprocess.run(
            ["powershell", "-NoProfile", "-Command",
             f"(Get-CimInstance Win32_Process -Filter 'ProcessId={pid}').CommandLine"],
            capture_output=True, text=True, encoding="gbk", errors="replace", timeout=10,
        )
        out = (r.stdout or "").strip()
        return out or None
    except Exception:
        return None


def main():
    parser = argparse.ArgumentParser(description="Get Jobs Auto 启动器")
    parser.add_argument("--clean-port", action="store_true",
                        help="仅当占用 8888 的进程是本软件残留时，结束它再启动")
    args = parser.parse_args()

    from app.config import settings
    from app.core import doctor

    print(f"""
============================================================
        Get Jobs Auto - 自动化求职投递工具
============================================================
  服务地址: http://{settings.host}:{settings.port}
  API 文档: http://{settings.host}:{settings.port}/docs
  支持平台: Boss直聘 / 51job / 智联 / 猎聘
============================================================
""")

    # ---- 1. 启动前环境自检（打印完整中文报告）----
    items = doctor.run_all(settings.host, settings.port, settings.chrome_debug_port)
    doctor.print_report(items)

    # ---- 2. 端口 8888 专项处理 ----
    port_state = doctor.inspect_port(settings.host, settings.port)

    if port_state["status"] == "ours":
        print("\n[启动] 本软件已在运行，正在打开页面，不重复启动。")
        webbrowser.open(f"http://{settings.host}:{settings.port}")
        sys.exit(0)

    if port_state["status"] == "occupied":
        pid = port_state.get("pid")
        name = port_state.get("process_name") or "未知进程"
        freed = False

        if args.clean_port and pid:
            cmdline = _cmdline_of_pid(pid)
            if cmdline and ("run.py" in cmdline or "app.main:app" in cmdline):
                print(f"\n[启动] 确认 PID={pid} 是本软件残留进程，正在结束...")
                subprocess.run(["taskkill", "/PID", str(pid), "/F"],
                               capture_output=True, timeout=10)
                time.sleep(1.5)
                freed = doctor.inspect_port(settings.host, settings.port)["status"] == "free"

        if not freed:
            if args.clean_port and pid:
                print(f"\n[启动中止] 端口仍被 PID={pid}（{name}）占用；"
                      "无法确认是本软件残留，为避免误杀未结束该进程。")
            else:
                print(f"\n[启动中止] 8888 端口被其它程序占用：PID={pid}（{name}）。")
            print("  处理方式：")
            print("  1. 手动关闭占用程序后重试；")
            print("  2. 若确认是本软件上次退出残留，运行: py -3.12 run.py --clean-port")
            sys.exit(1)

    # ---- 3. 其它致命项（Python / 依赖 / 浏览器 / 目录 / 数据库连接）----
    fatal = [i for i in items if i.level == "error" and not i.name.startswith("服务端口")]
    if fatal:
        print("\n[启动中止] 环境存在致命问题，请按上面报告中的建议修复后再启动。")
        sys.exit(1)

    # ---- 4. 启动服务 ----
    import uvicorn
    uvicorn.run(
        "app.main:app",
        host=settings.host,
        port=settings.port,
        reload=False,
        log_level="info"
    )


if __name__ == "__main__":
    main()
