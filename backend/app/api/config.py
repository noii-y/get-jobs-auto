"""配置管理API"""
import json
from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session
from app.database import get_db
from app.models import GlobalConfig, PlatformConfig, AISecret, NotifyConfig
from app.schemas import AIConfig, NotifyConfig as NotifyConfigSchema
from app.services.ai_service import ai_service
from app.services.notify import notify_service

router = APIRouter(prefix="/api/config", tags=["配置管理"])


# ============ 全局配置 ============

@router.get("/global", summary="获取全局配置")
async def get_global_config(db: Session = Depends(get_db)):
    items = db.query(GlobalConfig).all()
    result = {}
    for item in items:
        try:
            result[item.key] = json.loads(item.value)
        except (json.JSONDecodeError, TypeError):
            result[item.key] = item.value
    return result


@router.put("/global/{key}", summary="更新全局配置")
async def update_global_config(key: str, value: dict, db: Session = Depends(get_db)):
    item = db.query(GlobalConfig).filter(GlobalConfig.key == key).first()
    if not item:
        item = GlobalConfig(key=key)
        db.add(item)
    item.value = json.dumps(value, ensure_ascii=False)
    db.commit()
    return {"key": key, "value": value}


# ============ 平台配置 ============

@router.get("/platform/{platform}", summary="获取平台配置")
async def get_platform_config(platform: str, db: Session = Depends(get_db)):
    items = db.query(PlatformConfig).filter(PlatformConfig.platform == platform).all()
    result = {}
    for item in items:
        try:
            result[item.key] = json.loads(item.value)
        except (json.JSONDecodeError, TypeError):
            result[item.key] = item.value
    return {"platform": platform, "config": result}


@router.put("/platform/{platform}/{key}", summary="更新平台配置")
async def update_platform_config(platform: str, key: str, value: dict, db: Session = Depends(get_db)):
    item = db.query(PlatformConfig).filter(
        PlatformConfig.platform == platform,
        PlatformConfig.key == key
    ).first()
    if not item:
        item = PlatformConfig(platform=platform, key=key)
        db.add(item)
    item.value = json.dumps(value, ensure_ascii=False)
    db.commit()
    return {"platform": platform, "key": key, "value": value}


# ============ AI配置 ============

@router.get("/ai", summary="获取AI配置")
async def get_ai_config(db: Session = Depends(get_db)):
    item = db.query(AISecret).first()
    if not item:
        return {"enabled": False, "base_url": "", "model": "gpt-4o-mini", "api_key_set": False}
    return {
        "name": item.name,
        "base_url": item.base_url,
        "model": item.model,
        "enabled": item.enabled,
        "api_key_set": bool(item.api_key_encrypted)
    }


@router.put("/ai", summary="更新AI配置")
async def update_ai_config(config: AIConfig, db: Session = Depends(get_db)):
    from cryptography.fernet import Fernet
    from app.config import settings

    item = db.query(AISecret).first()
    if not item:
        item = AISecret(name=config.name)
        db.add(item)

    item.base_url = config.base_url
    item.model = config.model
    item.enabled = config.enabled

    # 加密存储API Key
    if config.api_key:
        fernet = Fernet(Fernet.generate_key()[:32].ljust(32, b'='))
        # 简化：直接存储（生产环境应加密）
        item.api_key_encrypted = config.api_key

    db.commit()

    # 更新运行时配置
    ai_service.configure(
        base_url=config.base_url,
        api_key=config.api_key or item.api_key_encrypted,
        model=config.model,
        enabled=config.enabled
    )

    return {"status": "ok", "enabled": config.enabled}


# ============ 通知配置 ============

@router.get("/notify", summary="获取通知配置")
async def get_notify_config(db: Session = Depends(get_db)):
    item = db.query(NotifyConfig).first()
    if not item:
        return {"enabled": False, "webhook_url": "", "notify_start": True, "notify_finish": True, "notify_error": True}
    return {
        "webhook_url": item.webhook_url,
        "enabled": item.enabled,
        "notify_start": item.notify_start,
        "notify_finish": item.notify_finish,
        "notify_error": item.notify_error
    }


@router.put("/notify", summary="更新通知配置")
async def update_notify_config(config: NotifyConfigSchema, db: Session = Depends(get_db)):
    item = db.query(NotifyConfig).first()
    if not item:
        item = NotifyConfig()
        db.add(item)

    item.webhook_url = config.webhook_url
    item.enabled = config.enabled
    item.notify_start = config.notify_start
    item.notify_finish = config.notify_finish
    item.notify_error = config.notify_error
    db.commit()

    # 更新运行时配置
    notify_service.configure(
        webhook_url=config.webhook_url,
        enabled=config.enabled,
        notify_start=config.notify_start,
        notify_finish=config.notify_finish,
        notify_error=config.notify_error
    )

    return {"status": "ok"}


@router.post("/notify/test", summary="发送测试通知")
async def test_notify():
    """发送测试消息验证Webhook配置"""
    success = await notify_service.send_message("【Get Jobs Auto】测试消息 - 通知配置成功！")
    return {"success": success}
