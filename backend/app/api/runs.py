"""任务运行相关API"""
import asyncio
import json
from typing import Optional
from fastapi import APIRouter, Depends, HTTPException, Query
from fastapi.responses import StreamingResponse
from sqlalchemy.orm import Session
from sse_starlette.sse import EventSourceResponse

from app.database import get_db
from app.models import Run, Task
from app.schemas import TaskCreate, TaskResponse, RunResponse
from app.core.scheduler import scheduler
from app.core.events import event_manager
from app.services.notify import notify_service

router = APIRouter(prefix="/api/runs", tags=["任务运行"])


@router.post("/start", summary="启动投递任务")
async def start_run(platform: str = Query(..., description="平台: boss/job51"),
                    keyword: str = Query("", description="搜索关键词"),
                    city: str = Query("", description="城市"),
                    salary: str = Query("", description="薪资范围"),
                    max_pages: int = Query(5, description="最大投递页数"),
                    say_hi: str = Query("", description="默认打招呼语"),
                    use_ai: bool = Query(False, description="是否使用AI生成打招呼语"),
                    filter_inactive_hr: bool = Query(True, description="Boss直聘: 是否过滤不活跃HR"),
                    hr_active_days: int = Query(3, description="Boss直聘: 只投递N天内活跃的HR"),
                    experience: str = Query("", description="Boss直聘: 工作经验"),
                    degree: str = Query("", description="Boss直聘: 学历要求"),
                    enable_company_check: bool = Query(True, description="是否启用公司背调"),
                    db: Session = Depends(get_db)):
    """启动一个投递任务"""
    if platform not in scheduler.get_available_platforms():
        raise HTTPException(status_code=400, detail=f"不支持的平台: {platform}")

    config = {
        "keyword": keyword,
        "city": city,
        "salary": salary,
        "max_pages": max_pages,
        "say_hi": say_hi,
        "use_ai": use_ai,
        "filter_inactive_hr": filter_inactive_hr,
        "hr_active_days": hr_active_days,
        "experience": experience,
        "degree": degree,
        "enable_company_check": enable_company_check,
    }

    run_id = await scheduler.start_run(platform=platform, config=config)

    # 发送开始通知
    await notify_service.notify_task_start(platform, config)

    return {"run_id": run_id, "platform": platform, "status": "running"}


@router.post("/{run_id}/stop", summary="停止投递任务")
async def stop_run(run_id: int):
    """停止运行中的任务"""
    if not scheduler.is_running(run_id):
        raise HTTPException(status_code=404, detail="任务不存在或已结束")
    scheduler.stop_run(run_id)
    return {"run_id": run_id, "status": "stopping"}


@router.get("/platforms", summary="获取支持的平台列表")
async def get_platforms():
    """获取已注册的投递平台"""
    return {"platforms": scheduler.get_available_platforms()}


@router.get("/{run_id}", summary="获取任务运行状态")
async def get_run(run_id: int, db: Session = Depends(get_db)):
    """获取任务运行详情"""
    run = db.query(Run).filter(Run.id == run_id).first()
    if not run:
        raise HTTPException(status_code=404, detail="任务不存在")
    return {
        "id": run.id,
        "platform": run.platform,
        "status": run.status,
        "total_count": run.total_count,
        "success_count": run.success_count,
        "failed_count": run.failed_count,
        "skipped_count": run.skipped_count,
        "fail_reason": getattr(run, "fail_reason", "") or "",
        "error_message": getattr(run, "error_message", "") or "",
        "cards_found": getattr(run, "cards_found", 0) or 0,
        "log_path": getattr(run, "log_path", "") or "",
        "started_at": run.started_at,
        "finished_at": run.finished_at,
        "is_running": scheduler.is_running(run_id)
    }


@router.get("", summary="获取任务列表")
async def list_runs(platform: Optional[str] = None,
                    limit: int = Query(20, le=100),
                    offset: int = 0,
                    db: Session = Depends(get_db)):
    """获取历史运行列表"""
    query = db.query(Run)
    if platform:
        query = query.filter(Run.platform == platform)
    runs = query.order_by(Run.started_at.desc()).offset(offset).limit(limit).all()
    return [
        {
            "id": r.id,
            "platform": r.platform,
            "status": r.status,
            "total_count": r.total_count,
            "success_count": r.success_count,
            "failed_count": r.failed_count,
            "fail_reason": getattr(r, "fail_reason", "") or "",
            "error_message": getattr(r, "error_message", "") or "",
            "cards_found": getattr(r, "cards_found", 0) or 0,
            "started_at": r.started_at,
            "finished_at": r.finished_at
        }
        for r in runs
    ]


@router.get("/{run_id}/events", summary="订阅任务实时事件(SSE)")
async def run_events(run_id: int):
    """SSE实时推送任务事件"""
    queue = event_manager.subscribe(run_id=run_id)

    async def event_generator():
        try:
            while True:
                try:
                    data = await asyncio.wait_for(queue.get(), timeout=30.0)
                    yield {"event": "message", "data": data}
                except asyncio.TimeoutError:
                    # 心跳
                    yield {"event": "ping", "data": "keep-alive"}
        except asyncio.CancelledError:
            pass
        finally:
            event_manager.unsubscribe(queue, run_id=run_id)

    return EventSourceResponse(event_generator())
