"""数据模型定义"""
import json
from datetime import datetime
from sqlalchemy import Column, Integer, String, Text, DateTime, Boolean, Float
from app.database import Base


class PlatformConfig(Base):
    """平台配置表"""
    __tablename__ = "platform_config"

    id = Column(Integer, primary_key=True, index=True)
    platform = Column(String(50), index=True, nullable=False)  # boss / job51
    key = Column(String(100), nullable=False)
    value = Column(Text, default="")  # JSON字符串存储
    created_at = Column(DateTime, default=datetime.now)
    updated_at = Column(DateTime, default=datetime.now, onupdate=datetime.now)


class GlobalConfig(Base):
    """全局配置表"""
    __tablename__ = "global_config"

    id = Column(Integer, primary_key=True, index=True)
    key = Column(String(100), unique=True, nullable=False)
    value = Column(Text, default="")
    created_at = Column(DateTime, default=datetime.now)
    updated_at = Column(DateTime, default=datetime.now, onupdate=datetime.now)


class Task(Base):
    """投递任务表"""
    __tablename__ = "task"

    id = Column(Integer, primary_key=True, index=True)
    platform = Column(String(50), index=True, nullable=False)
    name = Column(String(200), default="")
    config_json = Column(Text, default="{}")  # 任务配置（关键词、城市、薪资等）
    status = Column(String(20), default="pending")  # pending/running/completed/failed/stopped
    created_at = Column(DateTime, default=datetime.now)
    updated_at = Column(DateTime, default=datetime.now, onupdate=datetime.now)


class Run(Base):
    """运行实例表"""
    __tablename__ = "run"

    id = Column(Integer, primary_key=True, index=True)
    task_id = Column(Integer, index=True)
    platform = Column(String(50), index=True)
    status = Column(String(20), default="running")  # running/completed/failed/stopped
    total_count = Column(Integer, default=0)
    success_count = Column(Integer, default=0)
    failed_count = Column(Integer, default=0)
    skipped_count = Column(Integer, default=0)
    started_at = Column(DateTime, default=datetime.now)
    finished_at = Column(DateTime, nullable=True)
    log_path = Column(String(500), default="")
    # 阶段A 可观测：run 级失败原因与统计（均可空，带默认值）
    fail_reason = Column(String(100), nullable=True, default="")  # run 级失败原因码
    error_message = Column(String(500), nullable=True, default="")  # run 级异常摘要
    cards_found = Column(Integer, nullable=True, default=0)  # 列表页实际抓到的卡片数


class JobResult(Base):
    """投递结果表"""
    __tablename__ = "job_result"

    id = Column(Integer, primary_key=True, index=True)
    run_id = Column(Integer, index=True)
    platform = Column(String(50), index=True)
    job_title = Column(String(200), default="")
    company = Column(String(200), default="")
    salary = Column(String(100), default="")
    city = Column(String(100), default="")
    recruiter = Column(String(100), default="")
    job_url = Column(String(500), default="")
    status = Column(String(20), default="pending")  # success/failed/skipped
    message = Column(Text, default="")
    ai_greeting = Column(Text, default="")
    created_at = Column(DateTime, default=datetime.now)
    # 阶段A 可观测：单条投递失败的结构化原因（均可空，带默认值）
    reason_code = Column(String(50), nullable=True, default="")  # 机器可读失败码
    error_stage = Column(String(30), nullable=True, default="")  # 失败阶段
    error_url = Column(String(500), nullable=True, default="")  # 失败时页面 URL
    screenshot_path = Column(String(500), nullable=True, default="")  # 失败截图相对路径
    selector_used = Column(String(200), nullable=True, default="")  # 最后命中/未命中的选择器
    traceback_short = Column(String(1000), nullable=True, default="")  # 截断堆栈


class Blacklist(Base):
    """企业黑名单表"""
    __tablename__ = "blacklist"

    id = Column(Integer, primary_key=True, index=True)
    company_name = Column(String(200), index=True, nullable=False)
    platform = Column(String(50), default="")
    reason = Column(String(500), default="")
    source = Column(String(50), default="manual")  # manual/auto
    created_at = Column(DateTime, default=datetime.now)


class AISecret(Base):
    """AI配置表（敏感信息加密存储）"""
    __tablename__ = "ai_secret"

    id = Column(Integer, primary_key=True, index=True)
    name = Column(String(100), default="default")
    base_url = Column(String(500), default="")
    api_key_encrypted = Column(Text, default="")
    model = Column(String(100), default="gpt-4o-mini")
    enabled = Column(Boolean, default=False)
    created_at = Column(DateTime, default=datetime.now)
    updated_at = Column(DateTime, default=datetime.now, onupdate=datetime.now)


class NotifyConfig(Base):
    """通知配置表"""
    __tablename__ = "notify_config"

    id = Column(Integer, primary_key=True, index=True)
    webhook_url = Column(String(500), default="")
    enabled = Column(Boolean, default=False)
    notify_start = Column(Boolean, default=True)
    notify_finish = Column(Boolean, default=True)
    notify_error = Column(Boolean, default=True)
    created_at = Column(DateTime, default=datetime.now)


class Schedule(Base):
    """定时任务表"""
    __tablename__ = "schedule"

    id = Column(Integer, primary_key=True, index=True)
    name = Column(String(200), default="")  # 任务名称
    platform = Column(String(50), index=True, nullable=False)  # boss / job51
    config_json = Column(Text, default="{}")  # 投递配置（关键词、城市、薪资等）
    run_time = Column(String(10), default="09:00")  # 每天执行时间 HH:MM
    days_of_week = Column(String(20), default="0,1,2,3,4,5,6")  # 每周哪些天 0=周一...6=周日
    enabled = Column(Boolean, default=True)
    last_run_at = Column(DateTime, nullable=True)
    last_run_status = Column(String(20), default="")  # success/failed/skipped
    next_run_at = Column(DateTime, nullable=True)
    created_at = Column(DateTime, default=datetime.now)
    updated_at = Column(DateTime, default=datetime.now, onupdate=datetime.now)


class BatchJob(Base):
    """批量投递任务表（全平台一键投递）"""
    __tablename__ = "batch_job"

    id = Column(Integer, primary_key=True, index=True)
    name = Column(String(200), default="全平台投递")  # 任务名称
    keyword = Column(String(200), default="")  # 统一关键词
    city = Column(String(50), default="全国")  # 统一城市
    max_pages = Column(Integer, default=1)  # 每个平台最大页数
    say_hi = Column(String(500), default="")  # 打招呼语
    enable_company_check = Column(Boolean, default=True)  # 是否启用公司背调
    platforms = Column(String(200), default="")  # 平台列表，逗号分隔，如"boss,zhilian,liepin,job51"
    status = Column(String(20), default="pending")  # pending/running/completed/failed/stopped
    current_platform = Column(String(50), default="")  # 当前执行的平台
    total_runs = Column(Integer, default=0)  # 总子任务数
    completed_runs = Column(Integer, default=0)  # 已完成子任务数
    run_ids_json = Column(Text, default="{}")  # 各平台run_id映射 JSON
    started_at = Column(DateTime, nullable=True)
    finished_at = Column(DateTime, nullable=True)
    created_at = Column(DateTime, default=datetime.now)
    updated_at = Column(DateTime, default=datetime.now, onupdate=datetime.now)
