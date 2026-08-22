"""Pydantic数据模型（API请求/响应）"""
from datetime import datetime
from typing import Optional, Any, Dict, List
from pydantic import BaseModel, Field


# ============ 配置相关 ============

class GlobalConfigItem(BaseModel):
    key: str
    value: Any


class PlatformConfigItem(BaseModel):
    platform: str
    key: str
    value: Any


class AIConfig(BaseModel):
    name: str = "default"
    base_url: str = "https://api.openai.com/v1"
    api_key: str = ""
    model: str = "gpt-4o-mini"
    enabled: bool = False


class NotifyConfig(BaseModel):
    webhook_url: str = ""
    enabled: bool = False
    notify_start: bool = True
    notify_finish: bool = True
    notify_error: bool = True


# ============ 任务相关 ============

class TaskCreate(BaseModel):
    platform: str
    name: str = ""
    config: Dict[str, Any] = Field(default_factory=dict)


class TaskResponse(BaseModel):
    id: int
    platform: str
    name: str
    config: Dict[str, Any] = Field(default_factory=dict)
    status: str
    created_at: datetime
    updated_at: datetime

    class Config:
        from_attributes = True


class RunResponse(BaseModel):
    id: int
    task_id: Optional[int] = None
    platform: str
    status: str
    total_count: int = 0
    success_count: int = 0
    failed_count: int = 0
    skipped_count: int = 0
    started_at: datetime
    finished_at: Optional[datetime] = None

    class Config:
        from_attributes = True


class JobResultResponse(BaseModel):
    id: int
    run_id: int
    platform: str
    job_title: str
    company: str
    salary: str
    city: str
    recruiter: str
    job_url: str
    status: str
    message: str
    ai_greeting: str = ""
    created_at: datetime

    class Config:
        from_attributes = True


# ============ 黑名单相关 ============

class BlacklistCreate(BaseModel):
    company_name: str
    platform: str = ""
    reason: str = ""


class BlacklistResponse(BaseModel):
    id: int
    company_name: str
    platform: str
    reason: str
    source: str
    created_at: datetime

    class Config:
        from_attributes = True


# ============ 运行事件（SSE） ============

class RunEvent(BaseModel):
    """运行事件，用于SSE推送"""
    event_type: str  # log/progress/result/error/status
    run_id: Optional[int] = None
    platform: Optional[str] = None
    message: str = ""
    data: Dict[str, Any] = Field(default_factory=dict)
    timestamp: datetime = Field(default_factory=datetime.now)
