"""定时任务管理器 - 基于APScheduler实现每天固定时间自动投递"""
import json
import asyncio
from datetime import datetime, timedelta
from typing import Dict, List, Optional
from apscheduler.schedulers.background import BackgroundScheduler
from apscheduler.triggers.cron import CronTrigger
from app.database import SessionLocal
from app.models import Schedule
from app.core.scheduler import scheduler as run_scheduler
from app.services.notify import notify_service


class ScheduleManager:
    """定时任务管理器"""

    def __init__(self):
        self.scheduler = BackgroundScheduler(timezone="Asia/Shanghai")
        self._started = False

    def start(self):
        """启动定时任务调度器"""
        if self._started:
            return
        self.scheduler.start()
        self._started = True
        self._load_all_schedules()
        print("[定时任务] 调度器已启动")

    def shutdown(self):
        """关闭定时任务调度器"""
        if self._started:
            self.scheduler.shutdown(wait=False)
            self._started = False
            print("[定时任务] 调度器已关闭")

    def _load_all_schedules(self):
        """从数据库加载所有启用的定时任务"""
        db = SessionLocal()
        try:
            schedules = db.query(Schedule).filter(Schedule.enabled == True).all()
            for sched in schedules:
                self._add_job(sched)
            print(f"[定时任务] 已加载 {len(schedules)} 个定时任务")
        finally:
            db.close()

    def _add_job(self, schedule: Schedule):
        """添加一个定时任务到APScheduler"""
        job_id = f"schedule_{schedule.id}"
        # 解析时间
        try:
            hour, minute = map(int, schedule.run_time.split(":"))
        except (ValueError, AttributeError):
            hour, minute = 9, 0

        # 解析星期几
        try:
            days = schedule.days_of_week.split(",")
            day_of_week = ",".join(d.strip() for d in days if d.strip())
        except AttributeError:
            day_of_week = "mon-sun"

        trigger = CronTrigger(
            hour=hour,
            minute=minute,
            day_of_week=day_of_week,
            timezone="Asia/Shanghai"
        )

        self.scheduler.add_job(
            self._execute_schedule,
            trigger=trigger,
            args=[schedule.id],
            id=job_id,
            replace_existing=True,
            misfire_grace_time=3600  # 1小时内的错过任务仍然执行
        )

        # 更新下次执行时间
        self._update_next_run_time(schedule.id)

    def _remove_job(self, schedule_id: int):
        """从APScheduler移除定时任务"""
        job_id = f"schedule_{schedule_id}"
        try:
            self.scheduler.remove_job(job_id)
        except Exception:
            pass

    def _update_next_run_time(self, schedule_id: int):
        """更新下次执行时间"""
        db = SessionLocal()
        try:
            schedule = db.query(Schedule).filter(Schedule.id == schedule_id).first()
            if not schedule:
                return
            job_id = f"schedule_{schedule_id}"
            job = self.scheduler.get_job(job_id)
            if job and job.next_run_time:
                schedule.next_run_at = job.next_run_time.replace(tzinfo=None)
                db.commit()
        except Exception as e:
            print(f"[定时任务] 更新下次执行时间失败: {e}")
        finally:
            db.close()

    def _execute_schedule(self, schedule_id: int):
        """执行定时任务（在APScheduler线程中调用）"""
        print(f"[定时任务] 触发任务 #{schedule_id}")

        db = SessionLocal()
        try:
            schedule = db.query(Schedule).filter(Schedule.id == schedule_id).first()
            if not schedule or not schedule.enabled:
                return

            # 更新上次执行时间
            schedule.last_run_at = datetime.now()
            db.commit()

            # 解析配置
            try:
                config = json.loads(schedule.config_json) if schedule.config_json else {}
            except json.JSONDecodeError:
                config = {}

            # 启动投递任务（在新的事件循环中运行异步函数）
            platform = schedule.platform
            print(f"[定时任务] 启动 {platform} 投递: {config.get('keyword', '')}")

            # 发送通知
            try:
                asyncio.run(notify_service.notify_task_start(platform, config))
            except Exception as e:
                print(f"[定时任务] 发送开始通知失败: {e}")

            # 启动投递
            try:
                run_id = asyncio.run(run_scheduler.start_run(platform=platform, config=config))
                schedule.last_run_status = "running"
                db.commit()
                print(f"[定时任务] 投递任务已启动, run_id={run_id}")
            except Exception as e:
                schedule.last_run_status = "failed"
                db.commit()
                print(f"[定时任务] 启动投递失败: {e}")

            # 更新下次执行时间
            self._update_next_run_time(schedule_id)

        except Exception as e:
            print(f"[定时任务] 执行异常: {e}")
        finally:
            db.close()

    # ============ 对外接口 ============

    def list_schedules(self, platform: Optional[str] = None) -> List[Dict]:
        """获取所有定时任务"""
        db = SessionLocal()
        try:
            query = db.query(Schedule)
            if platform:
                query = query.filter(Schedule.platform == platform)
            schedules = query.order_by(Schedule.created_at.desc()).all()
            return [self._to_dict(s) for s in schedules]
        finally:
            db.close()

    def get_schedule(self, schedule_id: int) -> Optional[Dict]:
        """获取单个定时任务"""
        db = SessionLocal()
        try:
            schedule = db.query(Schedule).filter(Schedule.id == schedule_id).first()
            return self._to_dict(schedule) if schedule else None
        finally:
            db.close()

    def create_schedule(self, name: str, platform: str, config: Dict,
                        run_time: str = "09:00", days_of_week: str = "0,1,2,3,4,5,6",
                        enabled: bool = True) -> Dict:
        """创建定时任务"""
        db = SessionLocal()
        try:
            schedule = Schedule(
                name=name,
                platform=platform,
                config_json=json.dumps(config, ensure_ascii=False),
                run_time=run_time,
                days_of_week=days_of_week,
                enabled=enabled,
            )
            db.add(schedule)
            db.commit()
            db.refresh(schedule)

            if enabled:
                self._add_job(schedule)

            return self._to_dict(schedule)
        finally:
            db.close()

    def update_schedule(self, schedule_id: int, **kwargs) -> Optional[Dict]:
        """更新定时任务"""
        db = SessionLocal()
        try:
            schedule = db.query(Schedule).filter(Schedule.id == schedule_id).first()
            if not schedule:
                return None

            for key, value in kwargs.items():
                if key == "config" and value is not None:
                    schedule.config_json = json.dumps(value, ensure_ascii=False)
                elif hasattr(schedule, key) and value is not None:
                    setattr(schedule, key, value)

            db.commit()
            db.refresh(schedule)

            # 重新注册任务
            self._remove_job(schedule_id)
            if schedule.enabled:
                self._add_job(schedule)

            return self._to_dict(schedule)
        finally:
            db.close()

    def delete_schedule(self, schedule_id: int) -> bool:
        """删除定时任务"""
        db = SessionLocal()
        try:
            schedule = db.query(Schedule).filter(Schedule.id == schedule_id).first()
            if not schedule:
                return False
            self._remove_job(schedule_id)
            db.delete(schedule)
            db.commit()
            return True
        finally:
            db.close()

    def toggle_schedule(self, schedule_id: int, enabled: bool) -> Optional[Dict]:
        """启用/禁用定时任务"""
        return self.update_schedule(schedule_id, enabled=enabled)

    def run_now(self, schedule_id: int) -> Optional[Dict]:
        """立即执行一次定时任务"""
        db = SessionLocal()
        try:
            schedule = db.query(Schedule).filter(Schedule.id == schedule_id).first()
            if not schedule:
                return None
            # 在后台线程执行
            import threading
            t = threading.Thread(target=self._execute_schedule, args=(schedule_id,), daemon=True)
            t.start()
            return self._to_dict(schedule)
        finally:
            db.close()

    def _to_dict(self, schedule: Schedule) -> Dict:
        """转换为字典"""
        try:
            config = json.loads(schedule.config_json) if schedule.config_json else {}
        except json.JSONDecodeError:
            config = {}
        return {
            "id": schedule.id,
            "name": schedule.name,
            "platform": schedule.platform,
            "config": config,
            "run_time": schedule.run_time,
            "days_of_week": schedule.days_of_week,
            "enabled": schedule.enabled,
            "last_run_at": schedule.last_run_at.isoformat() if schedule.last_run_at else None,
            "last_run_status": schedule.last_run_status,
            "next_run_at": schedule.next_run_at.isoformat() if schedule.next_run_at else None,
            "created_at": schedule.created_at.isoformat() if schedule.created_at else None,
        }


# 全局单例
schedule_manager = ScheduleManager()
