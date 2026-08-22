"""批量任务管理器 - 管理全平台一键投递的串行执行和状态聚合"""
import asyncio
import json
from datetime import datetime
from typing import Dict, List, Optional
from app.database import SessionLocal
from app.models import BatchJob, Run, JobResult
from app.core.scheduler import scheduler
from app.core.events import event_manager
from app.schemas import RunEvent


class BatchManager:
    """批量投递任务管理器"""

    def __init__(self):
        self._active_batches: Dict[int, dict] = {}  # batch_id -> batch state
        self._platform_runners: Dict[int, str] = {}  # run_id -> platform

    async def start_batch(self, keyword: str, city: str, max_pages: int = 1,
                          say_hi: str = "", enable_company_check: bool = True,
                          platforms: List[str] = None,
                          max_retries: int = 1) -> int:
        """启动批量投递任务（串行执行）

        Args:
            max_retries: 单个平台失败后的最大重试次数，默认1
        """
        if not platforms:
            platforms = scheduler.get_available_platforms()

        # 创建批量任务记录
        db = SessionLocal()
        try:
            batch = BatchJob(
                keyword=keyword,
                city=city,
                max_pages=max_pages,
                say_hi=say_hi,
                enable_company_check=enable_company_check,
                platforms=",".join(platforms),
                status="running",
                total_runs=len(platforms),
                completed_runs=0,
                started_at=datetime.now(),
            )
            db.add(batch)
            db.commit()
            db.refresh(batch)
            batch_id = batch.id
        finally:
            db.close()

        # 初始化批量任务状态
        self._active_batches[batch_id] = {
            "platforms": platforms,
            "current_idx": 0,
            "run_ids": {},                # platform -> latest run_id
            "all_run_ids": [],            # 所有 run_id（含重试）
            "retries": {},                # platform -> 已重试次数
            "platform_status": {},        # platform -> 最终状态
            "max_retries": max_retries,
            "config": {
                "keyword": keyword,
                "city": city,
                "max_pages": max_pages,
                "say_hi": say_hi,
                "enable_company_check": enable_company_check,
            },
            "batch_id": batch_id,
        }

        # 启动第一个平台
        await self._start_next_platform(batch_id)

        # 推送批量任务启动事件
        await event_manager.publish(RunEvent(
            event_type="batch_started",
            run_id=batch_id,
            platform="batch",
            message=f"批量任务已启动，共{len(platforms)}个平台",
            data={"batch_id": batch_id, "platforms": platforms, "keyword": keyword, "city": city}
        ))

        return batch_id

    async def _start_next_platform(self, batch_id: int):
        """启动下一个平台（串行执行）"""
        if batch_id not in self._active_batches:
            return

        batch = self._active_batches[batch_id]
        platforms = batch["platforms"]
        current_idx = batch["current_idx"]

        if current_idx >= len(platforms):
            # 所有平台完成
            await self._finish_batch(batch_id, "completed")
            return

        platform = platforms[current_idx]
        config = batch["config"]
        retry_count = batch["retries"].get(platform, 0)

        # 启动子任务（带启动级重试）
        run_id = None
        last_error = None
        for startup_attempt in range(2):  # 启动失败最多重试1次
            try:
                run_id = await scheduler.start_run(platform=platform, config=config)
                break
            except Exception as e:
                last_error = e
                if startup_attempt == 0:
                    await asyncio.sleep(2)

        if run_id is None:
            # 启动彻底失败
            if retry_count < batch["max_retries"]:
                batch["retries"][platform] = retry_count + 1
                await event_manager.publish(RunEvent(
                    event_type="batch_platform_retry",
                    run_id=batch_id,
                    platform="batch",
                    message=f"{platform} 启动失败，准备重试({retry_count + 1}/{batch['max_retries']})",
                    data={"batch_id": batch_id, "platform": platform,
                          "retry": retry_count + 1, "max_retries": batch["max_retries"]}
                ))
                await asyncio.sleep(3)
                await self._start_next_platform(batch_id)
            else:
                batch["platform_status"][platform] = "failed"
                batch["current_idx"] += 1
                await event_manager.publish(RunEvent(
                    event_type="batch_platform_failed",
                    run_id=batch_id,
                    platform="batch",
                    message=f"{platform} 启动失败: {last_error}",
                    data={"batch_id": batch_id, "platform": platform, "error": str(last_error)}
                ))
                await self._start_next_platform(batch_id)
            return

        batch["run_ids"][platform] = run_id
        batch["all_run_ids"].append(run_id)
        self._platform_runners[run_id] = platform

        # 更新批量任务当前平台
        db = SessionLocal()
        try:
            batch_record = db.query(BatchJob).filter(BatchJob.id == batch_id).first()
            if batch_record:
                batch_record.current_platform = platform
                batch_record.run_ids_json = json.dumps(batch["run_ids"])
                db.commit()
        finally:
            db.close()

        # 设置runner的batch_id
        runner = scheduler.get_runner(run_id)
        if runner:
            runner.batch_id = batch_id
            await runner.update_status(action="搜索中", page=1)

        # 推送平台启动事件
        retry_msg = f"（第{retry_count + 1}次尝试）" if retry_count > 0 else ""
        await event_manager.publish(RunEvent(
            event_type="batch_platform_started",
            run_id=batch_id,
            platform="batch",
            message=f"开始执行 {platform}{retry_msg}",
            data={"batch_id": batch_id, "platform": platform, "run_id": run_id,
                  "index": current_idx, "retry": retry_count}
        ))

        # 监听子任务完成
        asyncio.create_task(self._watch_run(batch_id, run_id, platform))

    async def _watch_run(self, batch_id: int, run_id: int, platform: str):
        """监听子任务完成状态"""
        while True:
            await asyncio.sleep(2)
            runner = scheduler.get_runner(run_id)
            if not runner or getattr(runner, '_stopped', False):
                break
            if batch_id not in self._active_batches:
                return

        if batch_id not in self._active_batches:
            return

        # 等待runner线程完全结束（更新数据库状态），最多等15秒
        for _ in range(30):
            if not scheduler.is_running(run_id):
                break
            await asyncio.sleep(0.5)

        batch = self._active_batches[batch_id]

        # 查询子任务最终状态
        db = SessionLocal()
        try:
            run_record = db.query(Run).filter(Run.id == run_id).first()
            run_status = run_record.status if run_record else "unknown"
            # 如果数据库仍显示running，说明线程还在收尾，根据runner的final_status判断
            if run_status == "running":
                runner = scheduler.get_runner(run_id)
                if runner and hasattr(runner, 'final_status'):
                    run_status = runner.final_status
                else:
                    run_status = "stopped"  # 被手动停止的
        finally:
            db.close()

        # 判断是否需要重试：状态为 failed 且还有重试次数
        retry_count = batch["retries"].get(platform, 0)
        should_retry = (run_status == "failed" and retry_count < batch["max_retries"])

        if should_retry:
            # 重试当前平台（不递增 current_idx）
            batch["retries"][platform] = retry_count + 1
            await event_manager.publish(RunEvent(
                event_type="batch_platform_retry",
                run_id=batch_id,
                platform="batch",
                message=f"{platform} 执行失败，准备重试({retry_count + 1}/{batch['max_retries']})",
                data={"batch_id": batch_id, "platform": platform, "run_id": run_id,
                      "retry": retry_count + 1, "max_retries": batch["max_retries"]}
            ))
            await asyncio.sleep(3)
            await self._start_next_platform(batch_id)
            return

        # 当前平台结束（成功或重试耗尽）
        batch["platform_status"][platform] = run_status
        batch["current_idx"] += 1

        # 更新完成数
        db = SessionLocal()
        try:
            batch_record = db.query(BatchJob).filter(BatchJob.id == batch_id).first()
            if batch_record:
                batch_record.completed_runs = batch["current_idx"]
                db.commit()
        finally:
            db.close()

        # 推送平台完成事件
        event_type = "batch_platform_finished" if run_status == "completed" else "batch_platform_failed"
        await event_manager.publish(RunEvent(
            event_type=event_type,
            run_id=batch_id,
            platform="batch",
            message=f"{platform} {run_status}",
            data={"batch_id": batch_id, "platform": platform, "run_id": run_id,
                  "status": run_status}
        ))

        # 启动下一个平台
        await self._start_next_platform(batch_id)

    async def _finish_batch(self, batch_id: int, status: str):
        """完成批量任务"""
        if batch_id in self._active_batches:
            del self._active_batches[batch_id]

        db = SessionLocal()
        try:
            batch_record = db.query(BatchJob).filter(BatchJob.id == batch_id).first()
            if batch_record:
                batch_record.status = status
                batch_record.finished_at = datetime.now()
                db.commit()
        finally:
            db.close()

        await event_manager.publish(RunEvent(
            event_type="batch_finished",
            run_id=batch_id,
            platform="batch",
            message=f"批量任务{status}",
            data={"batch_id": batch_id, "status": status}
        ))

    def get_batch_status(self, batch_id: int) -> Optional[dict]:
        """获取批量任务状态（聚合各平台实时状态）"""
        db = SessionLocal()
        try:
            batch_record = db.query(BatchJob).filter(BatchJob.id == batch_id).first()
            if not batch_record:
                return None

            run_ids = json.loads(batch_record.run_ids_json) if batch_record.run_ids_json else {}
            platforms_status = []

            for platform, run_id in run_ids.items():
                runner = scheduler.get_runner(run_id)
                run_record = db.query(Run).filter(Run.id == run_id).first()

                if runner and not getattr(runner, '_stopped', False):
                    # 运行中，获取实时状态
                    stats = runner.get_stats()
                    platforms_status.append({
                        "platform": platform,
                        "run_id": run_id,
                        "status": "running",
                        "current_page": stats.get("current_page", 0),
                        "current_index": stats.get("current_index", 0),
                        "current_total": stats.get("current_total", 0),
                        "current_company": stats.get("current_company", ""),
                        "current_job": stats.get("current_job", ""),
                        "current_action": stats.get("current_action", ""),
                        "total_count": stats.get("total", 0),
                        "success_count": stats.get("success", 0),
                        "failed_count": stats.get("failed", 0),
                        "skipped_count": stats.get("skipped", 0),
                        "is_paused": stats.get("is_paused", False),
                    })
                elif runner and getattr(runner, '_stopped', False):
                    # 已收到停止信号但线程未完全结束，使用final_status
                    stats = runner.get_stats()
                    final_st = getattr(runner, 'final_status', 'stopped')
                    platforms_status.append({
                        "platform": platform,
                        "run_id": run_id,
                        "status": final_st,
                        "current_page": 0,
                        "current_index": 0,
                        "current_total": 0,
                        "current_company": "",
                        "current_job": "",
                        "current_action": "已停止" if final_st == "stopped" else final_st,
                        "total_count": stats.get("total", 0),
                        "success_count": stats.get("success", 0),
                        "failed_count": stats.get("failed", 0),
                        "skipped_count": stats.get("skipped", 0),
                        "is_paused": False,
                    })
                elif run_record:
                    # 已完成
                    platforms_status.append({
                        "platform": platform,
                        "run_id": run_id,
                        "status": run_record.status,
                        "current_page": 0,
                        "current_index": 0,
                        "current_total": 0,
                        "current_company": "",
                        "current_job": "",
                        "current_action": run_record.status,
                        "total_count": run_record.total_count or 0,
                        "success_count": run_record.success_count or 0,
                        "failed_count": run_record.failed_count or 0,
                        "skipped_count": run_record.skipped_count or 0,
                        "is_paused": False,
                    })
                else:
                    platforms_status.append({
                        "platform": platform,
                        "run_id": run_id,
                        "status": "pending",
                        "current_action": "等待中",
                    })

            # 未开始的平台
            started_platforms = set(run_ids.keys())
            all_platforms = batch_record.platforms.split(",") if batch_record.platforms else []
            for platform in all_platforms:
                if platform not in started_platforms:
                    platforms_status.append({
                        "platform": platform,
                        "run_id": None,
                        "status": "pending",
                        "current_action": "等待中",
                    })

            return {
                "batch_id": batch_id,
                "name": batch_record.name,
                "keyword": batch_record.keyword,
                "city": batch_record.city,
                "status": batch_record.status,
                "current_platform": batch_record.current_platform,
                "total_runs": batch_record.total_runs,
                "completed_runs": batch_record.completed_runs,
                "platforms": platforms_status,
                "started_at": batch_record.started_at.isoformat() if batch_record.started_at else None,
                "finished_at": batch_record.finished_at.isoformat() if batch_record.finished_at else None,
            }
        finally:
            db.close()

    def get_batch_results(self, batch_id: int) -> Optional[dict]:
        """获取批量任务的投递结果汇总"""
        db = SessionLocal()
        try:
            batch_record = db.query(BatchJob).filter(BatchJob.id == batch_id).first()
            if not batch_record:
                return None

            run_ids = json.loads(batch_record.run_ids_json) if batch_record.run_ids_json else {}
            all_run_ids = list(run_ids.values())

            # 查询所有关联的投递结果
            results_query = db.query(JobResult).filter(JobResult.run_id.in_(all_run_ids)) if all_run_ids else db.query(JobResult).filter(False)
            all_results = results_query.all()

            # 按平台汇总
            platform_stats = {}
            total = success = failed = skipped = 0
            recent_results = []

            for r in all_results:
                if r.platform not in platform_stats:
                    platform_stats[r.platform] = {
                        "platform": r.platform,
                        "total": 0, "success": 0, "failed": 0, "skipped": 0,
                    }
                ps = platform_stats[r.platform]
                ps["total"] += 1
                total += 1
                if r.status == "success":
                    ps["success"] += 1
                    success += 1
                elif r.status == "failed":
                    ps["failed"] += 1
                    failed += 1
                elif r.status == "skipped":
                    ps["skipped"] += 1
                    skipped += 1

                # 收集最近50条结果明细
                if len(recent_results) < 50:
                    recent_results.append({
                        "id": r.id,
                        "platform": r.platform,
                        "job_title": r.job_title,
                        "company": r.company,
                        "salary": r.salary,
                        "city": r.city,
                        "status": r.status,
                        "message": r.message,
                        "created_at": r.created_at.isoformat() if r.created_at else None,
                    })

            return {
                "batch_id": batch_id,
                "keyword": batch_record.keyword,
                "city": batch_record.city,
                "status": batch_record.status,
                "summary": {
                    "total": total,
                    "success": success,
                    "failed": failed,
                    "skipped": skipped,
                },
                "platforms": list(platform_stats.values()),
                "recent_results": recent_results,
                "started_at": batch_record.started_at.isoformat() if batch_record.started_at else None,
                "finished_at": batch_record.finished_at.isoformat() if batch_record.finished_at else None,
            }
        finally:
            db.close()

    async def pause_platform(self, batch_id: int, platform: str) -> bool:
        """暂停指定平台"""
        if batch_id not in self._active_batches:
            return False
        run_id = self._active_batches[batch_id]["run_ids"].get(platform)
        if run_id:
            runner = scheduler.get_runner(run_id)
            if runner:
                runner.pause()
                await runner.update_status(action="已暂停")
                return True
        return False

    async def resume_platform(self, batch_id: int, platform: str) -> bool:
        """继续指定平台"""
        if batch_id not in self._active_batches:
            return False
        run_id = self._active_batches[batch_id]["run_ids"].get(platform)
        if run_id:
            runner = scheduler.get_runner(run_id)
            if runner:
                runner.resume()
                # resume() 已恢复暂停前的 action，直接推送当前状态
                await runner.update_status()
                return True
        return False

    async def stop_platform(self, batch_id: int, platform: str) -> bool:
        """停止指定平台"""
        if batch_id not in self._active_batches:
            return False
        run_id = self._active_batches[batch_id]["run_ids"].get(platform)
        if run_id:
            scheduler.stop_run(run_id)
            return True
        return False

    async def stop_batch(self, batch_id: int) -> bool:
        """停止整个批量任务"""
        if batch_id not in self._active_batches:
            return False

        # 停止所有运行中的平台
        for platform, run_id in self._active_batches[batch_id]["run_ids"].items():
            scheduler.stop_run(run_id)

        await self._finish_batch(batch_id, "stopped")
        return True

    def list_batches(self, limit: int = 20) -> list:
        """列出批量任务"""
        db = SessionLocal()
        try:
            batches = db.query(BatchJob).order_by(BatchJob.id.desc()).limit(limit).all()
            return [{
                "id": b.id,
                "name": b.name,
                "keyword": b.keyword,
                "city": b.city,
                "status": b.status,
                "current_platform": b.current_platform,
                "total_runs": b.total_runs,
                "completed_runs": b.completed_runs,
                "platforms": b.platforms,
                "started_at": b.started_at.isoformat() if b.started_at else None,
                "finished_at": b.finished_at.isoformat() if b.finished_at else None,
            } for b in batches]
        finally:
            db.close()


# 全局批量管理器实例
batch_manager = BatchManager()
