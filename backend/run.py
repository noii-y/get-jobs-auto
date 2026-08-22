"""一键启动脚本"""
import sys
import os
from pathlib import Path

# 切换到backend目录
backend_dir = Path(__file__).resolve().parent
os.chdir(backend_dir)
sys.path.insert(0, str(backend_dir))

import uvicorn
from app.config import settings

if __name__ == "__main__":
    print(f"""
╔══════════════════════════════════════════════════╗
║          Get Jobs Auto - 自动化求职投递工具        ║
║                                                  ║
║  服务地址: http://{settings.host}:{settings.port}            ║
║  API文档:  http://{settings.host}:{settings.port}/docs       ║
║                                                  ║
║  支持平台: Boss直聘 / 51job / 智联 / 猎聘        ║
╚══════════════════════════════════════════════════╝
    """)

    uvicorn.run(
        "app.main:app",
        host=settings.host,
        port=settings.port,
        reload=False,
        log_level="info"
    )
