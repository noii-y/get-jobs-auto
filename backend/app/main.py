"""FastAPI 应用入口"""
import os
import sys
from contextlib import asynccontextmanager
from pathlib import Path

# 确保项目根目录在path中
BASE_DIR = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(BASE_DIR))

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles
from fastapi.responses import FileResponse

from app.config import settings
from app.database import init_db
from app.core.scheduler import scheduler
from app.core.schedule_manager import schedule_manager
from app.api import runs, config, results, schedules, company_check, batch, screenshots


@asynccontextmanager
async def lifespan(app: FastAPI):
    """应用生命周期管理"""
    # 启动时
    print(f"\n{'='*60}")
    print(f"  {settings.app_name} v{settings.app_version}")
    print(f"  服务地址: http://{settings.host}:{settings.port}")
    print(f"{'='*60}\n")

    # 初始化数据库
    init_db()
    print("[初始化] 数据库初始化完成")

    # 前端构建产物检查（缺失只警告，API/docs 仍可用）
    frontend_dist = BASE_DIR.parent / "frontend" / "dist" / "index.html"
    if not frontend_dist.exists():
        print("[警告] 未找到前端构建产物 frontend/dist/index.html：管理页面不可用，")
        print("       但 API 与文档(/docs)仍可访问。如需页面请先执行 npm run build。")

    # 启动自愈：重置上次异常退出遗留的僵尸任务（只改状态，不删数据）
    try:
        from app.core.recovery import recover_zombies
        stats = recover_zombies()
        run_ids = stats.get("run_ids", [])
        batch_ids = stats.get("batch_ids", [])
        if run_ids or batch_ids:
            print("[恢复] 上次异常退出，启动自动恢复：")
            if run_ids:
                print(f"        run 任务已置为 failed 并补 finished_at: {', '.join('#' + str(i) for i in run_ids)}")
            if batch_ids:
                print(f"        batch_job 任务已置为 failed 并补 finished_at: {', '.join('#' + str(i) for i in batch_ids)}")
    except Exception as e:
        print(f"[恢复] 自动恢复失败（已跳过，不影响启动）: {e}")

    # 注册平台Runner
    from app.platforms.boss.boss_runner import BossRunner
    from app.platforms.job51.job51_runner import Job51Runner
    from app.platforms.zhilian.zhilian_runner import ZhilianRunner
    from app.platforms.liepin.liepin_runner import LiepinRunner
    scheduler.register_platform("boss", BossRunner)
    scheduler.register_platform("job51", Job51Runner)
    scheduler.register_platform("zhilian", ZhilianRunner)
    scheduler.register_platform("liepin", LiepinRunner)
    print(f"[初始化] 已注册平台: {scheduler.get_available_platforms()}")

    # 加载配置到服务
    from app.database import SessionLocal
    from app.models import AISecret, NotifyConfig as NotifyConfigModel
    from app.services.ai_service import ai_service
    from app.services.notify import notify_service

    db = SessionLocal()
    try:
        ai_config = db.query(AISecret).first()
        if ai_config and ai_config.enabled:
            ai_service.configure(
                base_url=ai_config.base_url,
                api_key=ai_config.api_key_encrypted,
                model=ai_config.model,
                enabled=True
            )
            print("[初始化] AI服务已启用")

        notify_config = db.query(NotifyConfigModel).first()
        if notify_config:
            notify_service.configure(
                webhook_url=notify_config.webhook_url,
                enabled=notify_config.enabled,
                notify_start=notify_config.notify_start,
                notify_finish=notify_config.notify_finish,
                notify_error=notify_config.notify_error
            )
            if notify_config.enabled:
                print("[初始化] 通知服务已启用")
    finally:
        db.close()

    # 启动定时任务调度器
    schedule_manager.start()

    print("[初始化] 服务启动完成\n")

    yield

    # 关闭时
    print("\n[关闭] 服务正在关闭...")
    schedule_manager.shutdown()


# 创建FastAPI应用
app = FastAPI(
    title=settings.app_name,
    version=settings.app_version,
    description="自动化求职投递工具 - 支持Boss直聘和51job",
    lifespan=lifespan
)

# CORS配置
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# 注册API路由
app.include_router(runs.router)
app.include_router(config.router)
app.include_router(results.router)
app.include_router(schedules.router)
app.include_router(company_check.router)
app.include_router(batch.router)
app.include_router(screenshots.router)


@app.get("/api/health", summary="健康检查")
async def health():
    """健康检查接口"""
    return {
        "status": "ok",
        "app": settings.app_name,
        "version": settings.app_version,
        "platforms": scheduler.get_available_platforms(),
        "active_runs": scheduler.get_active_runs()
    }


# 静态文件服务（前端构建产物）—— 必须放在所有API路由之后
# BASE_DIR 是 backend/ 目录，前端在同级的 frontend/ 目录
frontend_dist = BASE_DIR.parent / "frontend" / "dist"
if frontend_dist.exists():
    assets_dir = frontend_dist / "assets"
    if assets_dir.exists():
        app.mount("/assets", StaticFiles(directory=str(assets_dir)), name="assets")

    @app.get("/")
    async def serve_index():
        return FileResponse(str(frontend_dist / "index.html"))

    @app.get("/{path:path}")
    async def serve_spa(path: str):
        """SPA路由回退（API路径已由前面的路由处理，不会走到这里）"""
        file_path = frontend_dist / path
        if file_path.exists() and file_path.is_file():
            return FileResponse(str(file_path))
        return FileResponse(str(frontend_dist / "index.html"))


if __name__ == "__main__":
    import uvicorn
    uvicorn.run(
        "app.main:app",
        host=settings.host,
        port=settings.port,
        reload=settings.debug
    )
