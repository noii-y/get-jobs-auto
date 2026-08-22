"""批量投递任务API路由"""
import asyncio
from fastapi import APIRouter, HTTPException, Query
from typing import List, Optional
from sse_starlette.sse import EventSourceResponse
from app.core.batch_manager import batch_manager
from app.core.events import event_manager

router = APIRouter(prefix="/api/batch", tags=["批量投递"])


@router.post("/start", summary="启动全平台一键投递")
async def start_batch(
    keyword: str = Query(..., description="搜索关键词"),
    city: str = Query("全国", description="城市"),
    max_pages: int = Query(1, description="每个平台最大页数"),
    say_hi: str = Query("", description="打招呼语"),
    enable_company_check: bool = Query(True, description="是否启用公司背调"),
    platforms: Optional[str] = Query(None, description="平台列表，逗号分隔，默认全部"),
):
    """启动全平台一键投递（串行执行）"""
    platform_list = platforms.split(",") if platforms else None
    try:
        batch_id = await batch_manager.start_batch(
            keyword=keyword,
            city=city,
            max_pages=max_pages,
            say_hi=say_hi,
            enable_company_check=enable_company_check,
            platforms=platform_list,
        )
        return {"batch_id": batch_id, "status": "started"}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/{batch_id}", summary="获取批量任务状态")
async def get_batch_status(batch_id: int):
    """获取批量任务实时状态（聚合各平台状态）"""
    status = batch_manager.get_batch_status(batch_id)
    if not status:
        raise HTTPException(status_code=404, detail="批量任务不存在")
    return status


@router.get("", summary="列出批量任务")
async def list_batches(limit: int = Query(20, description="返回数量")):
    """列出批量任务列表"""
    return {"items": batch_manager.list_batches(limit)}


@router.post("/{batch_id}/platform/{platform}/pause", summary="暂停指定平台")
async def pause_platform(batch_id: int, platform: str):
    """暂停批量任务中指定平台的投递"""
    success = await batch_manager.pause_platform(batch_id, platform)
    if not success:
        raise HTTPException(status_code=404, detail="批量任务或平台不存在")
    return {"status": "paused", "platform": platform}


@router.post("/{batch_id}/platform/{platform}/resume", summary="继续指定平台")
async def resume_platform(batch_id: int, platform: str):
    """继续批量任务中指定平台的投递"""
    success = await batch_manager.resume_platform(batch_id, platform)
    if not success:
        raise HTTPException(status_code=404, detail="批量任务或平台不存在")
    return {"status": "resumed", "platform": platform}


@router.post("/{batch_id}/platform/{platform}/stop", summary="停止指定平台")
async def stop_platform(batch_id: int, platform: str):
    """停止批量任务中指定平台的投递"""
    success = await batch_manager.stop_platform(batch_id, platform)
    if not success:
        raise HTTPException(status_code=404, detail="批量任务或平台不存在")
    return {"status": "stopped", "platform": platform}


@router.post("/{batch_id}/stop", summary="停止整个批量任务")
async def stop_batch(batch_id: int):
    """停止整个批量任务（停止所有平台）"""
    success = await batch_manager.stop_batch(batch_id)
    if not success:
        raise HTTPException(status_code=404, detail="批量任务不存在或已结束")
    return {"status": "stopped", "batch_id": batch_id}


@router.get("/{batch_id}/events", summary="订阅批量任务实时事件(SSE)")
async def batch_events(batch_id: int):
    """SSE实时推送批量任务及各平台事件"""
    queue = event_manager.subscribe(run_id=batch_id)

    async def event_generator():
        try:
            while True:
                try:
                    data = await asyncio.wait_for(queue.get(), timeout=30.0)
                    yield {"event": "message", "data": data}
                except asyncio.TimeoutError:
                    yield {"event": "ping", "data": "keep-alive"}
        except asyncio.CancelledError:
            pass
        finally:
            event_manager.unsubscribe(queue, run_id=batch_id)

    return EventSourceResponse(event_generator())


@router.get("/{batch_id}/results", summary="获取批量任务投递结果汇总")
async def get_batch_results(batch_id: int):
    """获取批量任务关联的所有投递结果"""
    results = batch_manager.get_batch_results(batch_id)
    if results is None:
        raise HTTPException(status_code=404, detail="批量任务不存在")
    return results
