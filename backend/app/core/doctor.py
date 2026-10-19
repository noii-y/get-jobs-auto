# -*- coding: utf-8 -*-
"""环境自检核心模块（纯函数式，供 CLI 与未来 API 复用）。

每项检查返回一个 CheckItem：
  name       检查项中文名
  level      ok / warn / error
  detail     详情（发生了什么）
  suggestion 修复建议（仅 warn/error 时有内容）
"""
from __future__ import annotations

import importlib.util
import json
import socket
import sqlite3
import subprocess
import sys
import urllib.request
from dataclasses import dataclass, asdict
from datetime import datetime
from pathlib import Path
from typing import List, Optional

BACKEND_DIR = Path(__file__).resolve().parent.parent.parent  # backend/

# (import 时用的模块名, pip 包名)
REQUIRED_PACKAGES = [
    ("fastapi", "fastapi"),
    ("uvicorn", "uvicorn"),
    ("sqlalchemy", "sqlalchemy"),
    ("pydantic_settings", "pydantic-settings"),
    ("sse_starlette", "sse-starlette"),
    ("multipart", "python-multipart"),
    ("httpx", "httpx"),
    ("DrissionPage", "DrissionPage"),
    ("cryptography", "cryptography"),
    ("apscheduler", "APScheduler"),
    ("dotenv", "python-dotenv"),
    ("aiofiles", "aiofiles"),
    ("openpyxl", "openpyxl"),
]


@dataclass
class CheckItem:
    name: str
    level: str          # ok / warn / error
    detail: str = ""
    suggestion: str = ""

    def to_dict(self) -> dict:
        return asdict(self)


# ---------------------------------------------------------------- 基础工具

def _get_settings():
    """尽量读取应用配置；依赖缺失时返回 None（调用方自行降级）。"""
    try:
        from app.config import settings
        return settings
    except Exception:
        return None


def _db_path_from_settings(settings) -> Optional[Path]:
    """从 database_url 解析出 SQLite 文件路径。"""
    if settings is None:
        return None
    url = getattr(settings, "database_url", "") or ""
    if url.startswith("sqlite:///"):
        p = url[len("sqlite:///"):]
        return Path(p)
    return None


def _port_open(host: str, port: int) -> bool:
    """探测端口是否被占用（能连上即视为已被监听）。"""
    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
        s.settimeout(1.5)
        return s.connect_ex((host, port)) == 0


def _probe_health(base_url: str) -> bool:
    """访问 /api/health，返回正常 JSON 即判定为本软件。用标准库 urllib，避免 doctor 自身依赖缺失时崩溃。"""
    try:
        req = urllib.request.Request(base_url.rstrip("/") + "/api/health")
        with urllib.request.urlopen(req, timeout=2) as resp:
            if resp.status != 200:
                return False
            data = json.loads(resp.read().decode("utf-8", "replace"))
            return data.get("status") == "ok"
    except Exception:
        return False


def _pid_on_port(port: int) -> Optional[int]:
    """Windows: 通过 netstat 找出监听该端口的 PID。"""
    try:
        r = subprocess.run(
            ["netstat", "-ano", "-p", "tcp"],
            capture_output=True, text=True, encoding="gbk", errors="replace", timeout=10,
        )
        for line in (r.stdout or "").splitlines():
            line = line.strip()
            if (f":{port}" in line) and ("LISTENING" in line.upper()):
                parts = line.split()
                try:
                    return int(parts[-1])
                except ValueError:
                    continue
    except Exception:
        pass
    return None


def _process_name(pid: int) -> str:
    """Windows: 通过 tasklist 查进程名。"""
    try:
        r = subprocess.run(
            ["tasklist", "/FI", f"PID eq {pid}", "/FO", "CSV", "/NH"],
            capture_output=True, text=True, encoding="gbk", errors="replace", timeout=10,
        )
        out = (r.stdout or "").strip()
        if out and "INFO:" not in out.upper():
            return out.split(",")[0].strip().strip('"')
    except Exception:
        pass
    return ""


def inspect_port(host: str, port: int) -> dict:
    """端口状态总览：返回 free / ours / occupied 三种结论及 pid/进程名。"""
    if not _port_open(host, port):
        return {"status": "free"}
    if _probe_health(f"http://{host}:{port}"):
        return {"status": "ours"}
    pid = _pid_on_port(port)
    name = _process_name(pid) if pid else ""
    return {"status": "occupied", "pid": pid, "process_name": name}


# ---------------------------------------------------------------- 各项检查

def check_python_version() -> CheckItem:
    v = sys.version_info
    if v.major == 3 and v.minor == 12:
        return CheckItem("Python 版本", "ok", f"当前 {v.major}.{v.minor}.{v.micro}（要求 3.12.x）")
    return CheckItem(
        "Python 版本", "error",
        f"当前为 {v.major}.{v.minor}.{v.micro}，本项目要求 Python 3.12.x（3.13 不兼容）",
        "请安装 Python 3.12 后使用 py -3.12 启动：https://www.python.org/downloads/release/python-31210/",
    )


def check_dependencies() -> CheckItem:
    missing: List[str] = []
    for mod_name, pip_name in REQUIRED_PACKAGES:
        try:
            if importlib.util.find_spec(mod_name) is None:
                missing.append(pip_name)
        except Exception:
            missing.append(pip_name)
    if not missing:
        return CheckItem("关键依赖", "ok", f"共 {len(REQUIRED_PACKAGES)} 个关键依赖全部可导入")
    return CheckItem(
        "关键依赖", "error",
        "缺失: " + ", ".join(missing),
        "请在 backend 目录执行: py -3.12 -m pip install -r requirements.txt（start.bat 会自动安装）",
    )


def check_browser() -> CheckItem:
    try:
        from app.core.browser import find_chrome_path
        path = find_chrome_path()
    except Exception as e:
        return CheckItem("浏览器", "error", f"无法加载浏览器探测模块: {e}", "请先安装依赖后重试 doctor")
    if path:
        return CheckItem("浏览器", "ok", f"已找到 Chrome/Edge: {path}")
    return CheckItem(
        "浏览器", "error",
        "未找到 Chrome 或 Edge 浏览器",
        "请安装 Google Chrome: https://www.google.com/chrome/  或  Microsoft Edge: https://www.microsoft.com/edge",
    )


def check_server_port(host: str, port: int) -> CheckItem:
    state = inspect_port(host, port)
    if state["status"] == "free":
        return CheckItem("服务端口 8888", "ok", "端口空闲，可以启动")
    if state["status"] == "ours":
        return CheckItem(
            "服务端口 8888", "warn",
            "8888 端口已由本软件占用（/api/health 正常响应）",
            "本软件已在运行，请勿重复启动；如要新开窗口请先关闭旧服务",
        )
    pid = state.get("pid")
    name = state.get("process_name") or "未知进程"
    detail = f"8888 被其它程序占用 (PID={pid}, 进程={name})"
    if pid:
        detail += "；该程序并未提供本软件的 /api/health"
    return CheckItem(
        "服务端口 8888", "error", detail,
        f"请先结束占用进程: taskkill /PID {pid} /F ，或改用 --clean-port 仅结束本软件残留进程",
    )


def check_debug_port(debug_port: int) -> CheckItem:
    if _port_open("127.0.0.1", debug_port):
        return CheckItem("Chrome 调试端口 9222", "ok", "调试端口已开放（v1.x 接管模式可用）")
    return CheckItem(
        "Chrome 调试端口 9222", "warn",
        "9222 调试端口未开放（当前 v1.x 接管模式需要它）",
        "如使用 v1.x 接管模式，请先运行 start-chrome.bat 启动调试浏览器；v2.0 登录中心上线后将不再需要",
    )


def check_frontend_dist() -> CheckItem:
    dist_index = BACKEND_DIR.parent / "frontend" / "dist" / "index.html"
    if dist_index.exists():
        return CheckItem("前端产物", "ok", f"已找到 {dist_index}")
    return CheckItem(
        "前端产物", "warn",
        "未找到 frontend/dist/index.html（页面不可用）",
        "如需图形界面，请在 frontend 目录执行 npm install 后 npm run build；仅用 API/docs 可忽略此项",
    )


def _zombie_ids(conn: sqlite3.Connection) -> List[int]:
    rows = conn.execute(
        "SELECT id FROM run WHERE status='running' AND finished_at IS NULL"
    ).fetchall()
    return [r[0] for r in rows]


def _batch_zombie_ids(conn: sqlite3.Connection) -> List[int]:
    rows = conn.execute(
        "SELECT id FROM batch_job WHERE status='running'"
    ).fetchall()
    return [r[0] for r in rows]


def check_database() -> CheckItem:
    settings = _get_settings()
    db_path = _db_path_from_settings(settings) or (BACKEND_DIR / "data" / "getjobs.db")
    try:
        conn = sqlite3.connect(str(db_path), timeout=5)
        # 可写性测试：建临时表 -> 写 -> 删（不碰业务数据）
        conn.execute("CREATE TABLE IF NOT EXISTS _doctor_wtest (id INTEGER)")
        conn.execute("INSERT INTO _doctor_wtest (id) VALUES (1)")
        conn.execute("DROP TABLE _doctor_wtest")
        conn.commit()
    except Exception as e:
        return CheckItem("数据库", "error", f"无法连接或写入 {db_path}: {e}", "请检查该文件是否被其它程序独占或磁盘是否已满")
    try:
        zombie_runs = _zombie_ids(conn)
        zombie_batches = _batch_zombie_ids(conn)
    except Exception as e:
        conn.close()
        return CheckItem("数据库", "warn", f"连接正常，但读取任务状态失败: {e}", "可忽略，或重新执行 doctor")
    conn.close()
    if zombie_runs or zombie_batches:
        parts = []
        if zombie_runs:
            parts.append("run 僵尸任务: " + ", ".join(f"#{i}" for i in zombie_runs))
        if zombie_batches:
            parts.append("batch_job 僵尸任务: " + ", ".join(f"#{i}" for i in zombie_batches))
        return CheckItem(
            "数据库", "warn",
            "；".join(parts) + "（上次异常退出未正常结束）",
            "可执行 py -3.12 doctor.py --fix 自动修复；或直接重启服务，启动时会自动恢复",
        )
    return CheckItem("数据库", "ok", f"连接正常且可写，无僵尸任务 ({db_path.name})")


def check_directories() -> CheckItem:
    settings = _get_settings()
    data_dir = Path(getattr(settings, "data_dir", BACKEND_DIR / "data")) if settings else (BACKEND_DIR / "data")
    browser_data_dir = Path(getattr(settings, "browser_data_dir", BACKEND_DIR / "browser_data")) if settings else (BACKEND_DIR / "browser_data")
    problems: List[str] = []
    for d in (data_dir, browser_data_dir):
        try:
            d.mkdir(parents=True, exist_ok=True)  # 缺失自动创建
            test_file = d / "_doctor_wtest.tmp"
            test_file.write_text("ok", encoding="utf-8")
            test_file.unlink()
        except Exception as e:
            problems.append(f"{d} 不可写: {e}")
    if problems:
        return CheckItem("数据目录", "error", "；".join(problems), "请检查目录权限，必要时以管理员身份运行一次")
    return CheckItem("数据目录", "ok", f"data={data_dir}；browser_data={browser_data_dir}")


EMOJI = {"ok": "[OK]", "warn": "[警告]", "error": "[错误]"}


def print_report(items: List[CheckItem]) -> int:
    """打印中文检查报告，返回错误项数量。"""
    print("=" * 60)
    print("  Get Jobs Auto 环境自检 doctor")
    print("=" * 60)
    for i, it in enumerate(items, 1):
        print(f"[{i}/{len(items)}] {EMOJI[it.level]} {it.name}")
        if it.detail:
            print(f"      {it.detail}")
        if it.suggestion and it.level != "ok":
            print(f"      建议: {it.suggestion}")
    n_ok = sum(1 for x in items if x.level == "ok")
    n_warn = sum(1 for x in items if x.level == "warn")
    n_err = sum(1 for x in items if x.level == "error")
    print("-" * 60)
    print(f"汇总: 通过 {n_ok} 项, 警告 {n_warn} 项, 错误 {n_err} 项")
    if n_err:
        print("结论: 存在错误项，请按上面建议修复后再启动。")
    elif n_warn:
        print("结论: 可以启动，警告项不影响核心运行。")
    else:
        print("结论: 全部通过，可以启动。")
    return n_err


def run_all(host: str = "127.0.0.1", port: int = 8888, debug_port: int = 9222) -> List[CheckItem]:
    """执行全部检查，返回结构化结果列表。"""
    items: List[CheckItem] = []
    # 致命项先跑：Python / 依赖 / 浏览器
    items.append(check_python_version())
    items.append(check_dependencies())
    items.append(check_browser())
    # 运行环境
    items.append(check_server_port(host, port))
    items.append(check_debug_port(debug_port))
    items.append(check_frontend_dist())
    items.append(check_database())
    items.append(check_directories())
    return items
