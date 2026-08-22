"""公司背调相关API"""
from typing import Optional
from fastapi import APIRouter, Query
from pydantic import BaseModel
from app.services.company_check import company_check_service

router = APIRouter(prefix="/api/company-check", tags=["公司背调"])


class KeywordAdd(BaseModel):
    keyword: str
    level: str = "medium"


@router.get("/check", summary="检测公司风险")
async def check_company(company: str = Query(..., description="公司名称"),
                        job_title: str = Query("", description="职位名称")):
    """检测公司风险等级"""
    result = company_check_service.check_company(company, job_title)
    return result


@router.get("/keywords", summary="获取风险关键词列表")
async def list_keywords():
    """获取所有风险关键词"""
    keywords = company_check_service.get_all_keywords()
    return {"total": len(keywords), "items": keywords}


@router.post("/keywords", summary="添加自定义风险关键词")
async def add_keyword(data: KeywordAdd):
    """添加自定义风险关键词"""
    if data.level not in ["high", "medium", "low"]:
        return {"success": False, "message": "风险等级必须是 high/medium/low"}
    success = company_check_service.add_keyword(data.keyword, data.level)
    return {"success": success}


@router.delete("/keywords/{keyword}", summary="删除自定义风险关键词")
async def remove_keyword(keyword: str):
    """删除自定义风险关键词"""
    success = company_check_service.remove_keyword(keyword)
    return {"success": success}
