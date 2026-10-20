# -*- coding: utf-8 -*-
"""阶段A：失败截图与日志的只读访问路由。

安全约束：
- 只允许访问 settings.data_dir/screenshots 与 settings.data_dir/logs 内的文件。
- 对拼接后的绝对路径做 resolve 并校验仍在根目录内，拒绝 ../ 或绝对路径穿越。
- 非法路径返回 403/404；文件不存在返回 404。
"""
from pathlib import Path
from fastapi import APIRouter, HTTPException
from fastapi.responses import FileResponse
from app.config import settings

router = APIRouter(prefix="/api", tags=["失败截图与日志"])


def _safe_join(root_name: str, rel_path: str) -> Path:
    """把相对路径拼到 settings.data_dir/{root_name} 下并校验不越界。

    越界（含 ../、绝对路径、符号链接逃逸）一律 403。
    """
    root = (Path(settings.data_dir) / root_name).resolve()
    # 去掉可能的前导斜杠，避免被当作绝对路径
    rel = rel_path.lstrip("/\\")
    target = (root / rel).resolve()
    # 必须 target 在 root 之下（target == root 也允许，因为 root 是目录）
    if target != root and root not in target.parents:
        raise HTTPException(status_code=403, detail="非法路径")
    return target


@router.get("/screenshots/{run_id}/{filename}", summary="读取失败截图（只读）")
async def get_screenshot(run_id: int, filename: str):
    root = "screenshots"
    target = _safe_join(root, f"{run_id}/{filename}")
    if not target.exists() or not target.is_file():
        raise HTTPException(status_code=404, detail="截图不存在")
    return FileResponse(str(target), media_type="image/png")


@router.get("/logs/{run_id}", summary="读取 run 日志文件（只读）")
async def get_run_log(run_id: int):
    target = _safe_join("logs", f"run_{run_id}.log")
    if not target.exists() or not target.is_file():
        raise HTTPException(status_code=404, detail="日志不存在")
    return FileResponse(str(target), media_type="text/plain; charset=utf-8")
