"""任务调度器 - 管理投递任务的创建、执行、停止"""
import asyncio
import json
from datetime import datetime
from typing import Dict, Optional, Type
from sqlalchemy.orm import Session
from app.database import SessionLocal
from app.models import Run, Task
from app.core.runner_base import BaseRunner
from app.core.events import event_manager
from app.schemas import RunEvent


class TaskScheduler:
    """任务调度器"""

    def __init__(self):
        self._runners: Dict[int, BaseRunner] = {}  # run_id -> runner
        self._tasks: Dict[int, asyncio.Task] = {}  # run_id -> asyncio.Task
        self._platform_registry: Dict[str, Type[BaseRunner]] = {}

    def register_platform(self, platform: str, runner_class: Type[BaseRunner]):
        """注册平台Runner"""
        self._platform_registry[platform] = runner_class
        print(f"[Scheduler] 已注册平台: {platform}")

    def get_available_platforms(self) -> list:
        """获取已注册的平台列表"""
        return list(self._platform_registry.keys())

    async def start_run(self, platform: str, config: dict, task_id: int = None) -> int:
        """启动一个投递任务"""
        if platform not in self._platform_registry:
            raise ValueError(f"不支持的平台: {platform}，已注册: {list(self._platform_registry.keys())}")

        # 创建运行记录
        db = SessionLocal()
        try:
            run = Run(
                task_id=task_id,
                platform=platform,
                status="running",
                started_at=datetime.now()
            )
            db.add(run)
            db.commit()
            db.refresh(run)
            run_id = run.id
        finally:
            db.close()

        # 创建Runner并执行
        runner_class = self._platform_registry[platform]
        runner = runner_class(run_id=run_id, config=config)
        self._runners[run_id] = runner

        # 在后台线程中执行（因为DrissionPage是同步的）
        loop = asyncio.get_event_loop()
        task = loop.run_in_executor(None, self._run_runner_sync, runner, run_id)
        self._tasks[run_id] = task

        await event_manager.publish(RunEvent(
            event_type="status",
            run_id=run_id,
            platform=platform,
            message="任务已启动",
            data={"run_id": run_id}
        ))

        return run_id

    def _run_runner_sync(self, runner: BaseRunner, run_id: int):
        """同步执行Runner（在线程池中运行）"""
        try:
            # 创建新的事件循环来运行异步代码
            loop = asyncio.new_event_loop()
            asyncio.set_event_loop(loop)
            loop.run_until_complete(runner.run())
            loop.close()

            # 更新运行状态
            db = SessionLocal()
            try:
                run = db.query(Run).filter(Run.id == run_id).first()
                if run:
                    stats = runner.get_stats()
                    run.status = runner.final_status
                    run.total_count = stats["total"]
                    run.success_count = stats["success"]
                    run.failed_count = stats["failed"]
                    run.skipped_count = stats["skipped"]
                    run.finished_at = datetime.now()
                    db.commit()
            finally:
                db.close()

        except Exception as e:
            db = SessionLocal()
            try:
                run = db.query(Run).filter(Run.id == run_id).first()
                if run:
                    run.status = "failed"
                    run.finished_at = datetime.now()
                    db.commit()
            finally:
                db.close()

            # 推送错误事件
            loop = asyncio.new_event_loop()
            asyncio.set_event_loop(loop)
            loop.run_until_complete(event_manager.publish(RunEvent(
                event_type="error",
                run_id=run_id,
                platform=runner.platform,
                message=f"任务执行失败: {str(e)}"
            )))
            loop.close()
        finally:
            self._runners.pop(run_id, None)
            self._tasks.pop(run_id, None)

    def stop_run(self, run_id: int) -> bool:
        """停止运行中的任务"""
        if run_id in self._runners:
            self._runners[run_id].stop()
            return True
        return False

    def get_runner(self, run_id: int) -> Optional[BaseRunner]:
        """获取运行中的Runner"""
        return self._runners.get(run_id)

    def is_running(self, run_id: int) -> bool:
        """检查任务是否在运行"""
        return run_id in self._runners

    def get_active_runs(self) -> list:
        """获取所有运行中的任务ID"""
        return list(self._runners.keys())


# 全局调度器实例
scheduler = TaskScheduler()
