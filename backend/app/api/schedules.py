"""定时任务相关API"""
from typing import Optional, List, Dict, Any
from fastapi import APIRouter, HTTPException, Query
from pydantic import BaseModel
from app.core.schedule_manager import schedule_manager

router = APIRouter(prefix="/api/schedules", tags=["定时任务"])


class ScheduleCreate(BaseModel):
    name: str = ""
    platform: str
    config: Dict[str, Any] = {}
    run_time: str = "09:00"
    days_of_week: str = "0,1,2,3,4,5,6"
    enabled: bool = True


class ScheduleUpdate(BaseModel):
    name: Optional[str] = None
    config: Optional[Dict[str, Any]] = None
    run_time: Optional[str] = None
    days_of_week: Optional[str] = None
    enabled: Optional[bool] = None


@router.get("", summary="获取定时任务列表")
async def list_schedules(platform: Optional[str] = Query(None, description="按平台筛选")):
    """获取所有定时任务"""
    schedules = schedule_manager.list_schedules(platform=platform)
    return {"total": len(schedules), "items": schedules}


@router.get("/{schedule_id}", summary="获取定时任务详情")
async def get_schedule(schedule_id: int):
    """获取单个定时任务"""
    schedule = schedule_manager.get_schedule(schedule_id)
    if not schedule:
        raise HTTPException(status_code=404, detail="定时任务不存在")
    return schedule


@router.post("", summary="创建定时任务")
async def create_schedule(data: ScheduleCreate):
    """创建定时任务"""
    if data.platform not in ["boss", "job51"]:
        raise HTTPException(status_code=400, detail="不支持的平台")

    # 验证时间格式
    try:
        hour, minute = map(int, data.run_time.split(":"))
        if not (0 <= hour <= 23 and 0 <= minute <= 59):
            raise ValueError
    except (ValueError, AttributeError):
        raise HTTPException(status_code=400, detail="时间格式错误，应为 HH:MM")

    schedule = schedule_manager.create_schedule(
        name=data.name,
        platform=data.platform,
        config=data.config,
        run_time=data.run_time,
        days_of_week=data.days_of_week,
        enabled=data.enabled,
    )
    return schedule


@router.put("/{schedule_id}", summary="更新定时任务")
async def update_schedule(schedule_id: int, data: ScheduleUpdate):
    """更新定时任务"""
    # 验证时间格式
    if data.run_time:
        try:
            hour, minute = map(int, data.run_time.split(":"))
            if not (0 <= hour <= 23 and 0 <= minute <= 59):
                raise ValueError
        except (ValueError, AttributeError):
            raise HTTPException(status_code=400, detail="时间格式错误，应为 HH:MM")

    schedule = schedule_manager.update_schedule(schedule_id, **data.model_dump(exclude_none=True))
    if not schedule:
        raise HTTPException(status_code=404, detail="定时任务不存在")
    return schedule


@router.delete("/{schedule_id}", summary="删除定时任务")
async def delete_schedule(schedule_id: int):
    """删除定时任务"""
    success = schedule_manager.delete_schedule(schedule_id)
    if not success:
        raise HTTPException(status_code=404, detail="定时任务不存在")
    return {"status": "ok"}


@router.post("/{schedule_id}/toggle", summary="启用/禁用定时任务")
async def toggle_schedule(schedule_id: int, enabled: bool = Query(..., description="是否启用")):
    """启用或禁用定时任务"""
    schedule = schedule_manager.toggle_schedule(schedule_id, enabled)
    if not schedule:
        raise HTTPException(status_code=404, detail="定时任务不存在")
    return schedule


@router.post("/{schedule_id}/run", summary="立即执行定时任务")
async def run_schedule_now(schedule_id: int):
    """立即执行一次定时任务"""
    schedule = schedule_manager.run_now(schedule_id)
    if not schedule:
        raise HTTPException(status_code=404, detail="定时任务不存在")
    return {"status": "triggered", "schedule": schedule}
