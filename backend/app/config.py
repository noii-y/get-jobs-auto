"""应用配置管理"""
import os
from pathlib import Path
from pydantic_settings import BaseSettings

# 预计算基础目录（类定义时即可确定）
_base_dir = Path(__file__).resolve().parent.parent

# 自动检测便携版模式：上级目录存在 user-data 目录即为便携版
_portable_root = _base_dir.parent
_is_portable = (_portable_root / "user-data").exists() or os.environ.get("GETJOBS_PORTABLE") == "1"

if _is_portable:
    _data_dir = _portable_root / "user-data"
    _browser_data_dir = _portable_root / "user-data" / "chrome-data"
    _database_url = f"sqlite:///{_data_dir / 'getjobs.db'}"
else:
    _data_dir = _base_dir / "data"
    _browser_data_dir = _base_dir / "browser_data"
    _database_url = f"sqlite:///{_base_dir / 'data' / 'getjobs.db'}"


class Settings(BaseSettings):
    """应用全局配置"""

    # 服务配置
    app_name: str = "Get Jobs Auto - 自动化求职投递工具"
    app_version: str = "1.1.0"
    host: str = "127.0.0.1"
    port: int = 8888
    debug: bool = False

    # 运行模式
    is_portable: bool = _is_portable

    # 路径配置（直接设置默认值，避免None验证问题）
    base_dir: Path = _base_dir
    data_dir: Path = _data_dir
    browser_data_dir: Path = _browser_data_dir

    # 数据库
    database_url: str = _database_url

    # 浏览器配置
    chrome_debug_port: int = 9222  # 接管Chrome的调试端口
    browser_headless: bool = False  # 是否无头模式（建议False，反爬效果好）

    # 调度配置
    max_concurrent_runs: int = 1  # 最大同时运行任务数（建议1，避免风控）

    # 加密密钥（用于加密存储敏感信息）
    secret_key: str = "get-jobs-auto-secret-key-change-me"

    model_config = {"env_file": ".env", "env_file_encoding": "utf-8"}

    def __init__(self, **kwargs):
        super().__init__(**kwargs)
        # 确保目录存在
        self.data_dir.mkdir(parents=True, exist_ok=True)
        self.browser_data_dir.mkdir(parents=True, exist_ok=True)


settings = Settings()
