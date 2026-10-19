# -*- coding: utf-8 -*-
"""环境自检 CLI 入口。

用法:
  py -3.12 doctor.py          打印中文检查报告（有 error 时退出码为 1）
  py -3.12 doctor.py --json    机器可读 JSON 输出
  py -3.12 doctor.py --fix     先打印报告，再自动修复僵尸任务（run/batch_job 残留 running）
"""
import argparse
import json
import os
import sys
from pathlib import Path

# 切到 backend 目录，保证能 import app 包
backend_dir = Path(__file__).resolve().parent
os.chdir(backend_dir)
sys.path.insert(0, str(backend_dir))

try:
    sys.stdout.reconfigure(encoding="utf-8")
except Exception:
    pass

from app.core.doctor import run_all, print_report  # noqa: E402


def main():
    parser = argparse.ArgumentParser(description="Get Jobs Auto 环境自检")
    parser.add_argument("--json", action="store_true", help="输出机器可读 JSON")
    parser.add_argument("--fix", action="store_true", help="自动修复僵尸任务（残留 running）")
    parser.add_argument("--is-running", action="store_true",
                        help="仅检测本软件是否已在运行（供启动脚本调用；在运行则退出码 0）")
    args = parser.parse_args()

    # --is-running 模式：不打印完整报告，只给出退出码
    if args.is_running:
        from app.core import doctor
        try:
            from app.config import settings
            host, port = settings.host, settings.port
        except Exception:
            host, port = "127.0.0.1", 8888
        state = doctor.inspect_port(host, port)
        if state["status"] == "ours":
            print(f"本软件已在运行: http://{host}:{port}")
            sys.exit(0)
        sys.exit(1)

    items = run_all()
    n_err = sum(1 for x in items if x.level == "error")

    if args.json:
        print(json.dumps(
            {"items": [it.to_dict() for it in items], "error_count": n_err},
            ensure_ascii=False, indent=2,
        ))
    else:
        print_report(items)

    if args.fix:
        print("-" * 60)
        print("开始自动修复僵尸任务...")
        from app.core.recovery import recover_zombies
        try:
            stats = recover_zombies()
            run_ids = stats.get("run_ids", [])
            batch_ids = stats.get("batch_ids", [])
            if run_ids:
                print(f"  已将 run 任务置为 failed 并补 finished_at: {', '.join('#' + str(i) for i in run_ids)}")
            if batch_ids:
                print(f"  已将 batch_job 任务置为 failed 并补 finished_at: {', '.join('#' + str(i) for i in batch_ids)}")
            if not run_ids and not batch_ids:
                print("  没有发现僵尸任务，无需修复。")
        except Exception as e:
            print(f"  修复失败: {e}")

    sys.exit(1 if n_err else 0)


if __name__ == "__main__":
    main()
