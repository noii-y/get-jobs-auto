"""平台Runner基类 - 所有平台自动化脚本继承此类"""
import asyncio
import time
import random
from abc import ABC, abstractmethod
from datetime import datetime
from typing import Dict, Any, Optional, List
from app.core.events import event_manager
from app.schemas import RunEvent
from app.database import SessionLocal
from app.models import JobResult


class BaseRunner(ABC):
    """平台自动化执行器基类"""

    platform: str = "base"

    def __init__(self, run_id: int, config: Dict[str, Any]):
        self.run_id = run_id
        self.config = config
        self.page = None
        self.browser = None
        self.total_count = 0
        self.success_count = 0
        self.failed_count = 0
        self.skipped_count = 0
        self._stopped = False
        self._paused = False
        self._pre_pause_action = "等待中"  # 暂停前的动作，恢复时还原
        self.final_status = "completed"  # 最终状态，runner可通过status("failed")修改
        # 实时状态字段（用于批量任务监控）
        self.current_page = 0
        self.current_index = 0
        self.current_total = 0
        self.current_company = ""
        self.current_job = ""
        self.current_action = "等待中"  # 等待中/搜索中/投递中/沟通中/已完成
        self.batch_id = None  # 所属批量任务ID

    async def log(self, message: str, level: str = "info"):
        """记录日志并推送"""
        event = RunEvent(
            event_type="log",
            run_id=self.run_id,
            platform=self.platform,
            message=f"[{level.upper()}] {message}",
            data={"level": level, "batch_id": self.batch_id}
        )
        await event_manager.publish(event)
        print(f"[{self.platform}] {message}")

    async def progress(self, current: int, total: int, message: str = ""):
        """推送进度"""
        event = RunEvent(
            event_type="progress",
            run_id=self.run_id,
            platform=self.platform,
            message=message,
            data={"current": current, "total": total, "batch_id": self.batch_id}
        )
        await event_manager.publish(event)

    async def result(self, job_data: Dict[str, Any], status: str, message: str = "", ai_greeting: str = ""):
        """推送投递结果并持久化到数据库"""
        # 持久化到数据库（独立于SSE连接，确保批量模式也能保存）
        self._persist_result(job_data, status, message, ai_greeting)

        event = RunEvent(
            event_type="result",
            run_id=self.run_id,
            platform=self.platform,
            message=message,
            data={**job_data, "status": status, "ai_greeting": ai_greeting, "batch_id": self.batch_id}
        )
        await event_manager.publish(event)

    def _persist_result(self, job_data: Dict[str, Any], status: str, message: str, ai_greeting: str = ""):
        """将投递结果保存到数据库（同步方法，在线程中安全调用）"""
        try:
            db = SessionLocal()
            try:
                record = JobResult(
                    run_id=self.run_id,
                    platform=self.platform,
                    job_title=job_data.get("title", "") or job_data.get("job_title", ""),
                    company=job_data.get("company", ""),
                    salary=job_data.get("salary", ""),
                    city=job_data.get("city", ""),
                    recruiter=job_data.get("recruiter", ""),
                    job_url=job_data.get("job_url", ""),
                    status=status,
                    message=message,
                    ai_greeting=ai_greeting or "",
                )
                db.add(record)
                db.commit()
            finally:
                db.close()
        except Exception as e:
            print(f"[{self.platform}] 保存结果失败: {e}")

    async def error(self, message: str):
        """推送错误"""
        event = RunEvent(
            event_type="error",
            run_id=self.run_id,
            platform=self.platform,
            message=message,
            data={"batch_id": self.batch_id}
        )
        await event_manager.publish(event)

    async def status(self, status: str, data: Dict[str, Any] = None):
        """推送状态变更"""
        if status in ("failed", "completed", "stopped"):
            self.final_status = status
        event_data = data or {}
        event_data["batch_id"] = self.batch_id
        event = RunEvent(
            event_type="status",
            run_id=self.run_id,
            platform=self.platform,
            message=status,
            data=event_data
        )
        await event_manager.publish(event)

    def stop(self):
        """停止运行"""
        self._stopped = True
        self._paused = False
        self.final_status = "stopped"

    def pause(self):
        """暂停运行"""
        if not self._paused:
            self._pre_pause_action = self.current_action
        self._paused = True
        self.current_action = "已暂停"

    def resume(self):
        """继续运行"""
        self._paused = False
        # 恢复暂停前的动作（如果不是终态）
        if self._pre_pause_action and self._pre_pause_action != "已暂停":
            self.current_action = self._pre_pause_action
        else:
            self.current_action = "运行中"

    def is_paused(self) -> bool:
        """检查是否暂停"""
        return self._paused

    async def check_paused(self):
        """检查暂停状态，如果暂停则等待（在关键节点调用）。
        暂停期间每3秒推送一次心跳状态，确保前端能看到暂停态。"""
        if not self._paused:
            return
        heartbeat_count = 0
        while self._paused and not self._stopped:
            await asyncio.sleep(0.5)
            heartbeat_count += 1
            # 每6次循环（约3秒）推送一次暂停心跳
            if heartbeat_count % 6 == 0:
                try:
                    event = RunEvent(
                        event_type="realtime_status",
                        run_id=self.run_id,
                        platform=self.platform,
                        message="已暂停",
                        data={
                            "current_page": self.current_page,
                            "current_index": self.current_index,
                            "current_total": self.current_total,
                            "current_company": self.current_company,
                            "current_job": self.current_job,
                            "current_action": "已暂停",
                            "batch_id": self.batch_id,
                        }
                    )
                    await event_manager.publish(event)
                except Exception:
                    pass

    async def update_status(self, action: str = "", page: int = None, index: int = None,
                            total: int = None, company: str = None, job: str = None):
        """更新实时状态并推送事件"""
        if action:
            self.current_action = action
        if page is not None:
            self.current_page = page
        if index is not None:
            self.current_index = index
        if total is not None:
            self.current_total = total
        if company is not None:
            self.current_company = company
        if job is not None:
            self.current_job = job

        event = RunEvent(
            event_type="realtime_status",
            run_id=self.run_id,
            platform=self.platform,
            message=self.current_action,
            data={
                "current_page": self.current_page,
                "current_index": self.current_index,
                "current_total": self.current_total,
                "current_company": self.current_company,
                "current_job": self.current_job,
                "current_action": self.current_action,
                "batch_id": self.batch_id,
            }
        )
        await event_manager.publish(event)

    def random_sleep(self, min_sec: float = 1.0, max_sec: float = 3.0):
        """随机延时，模拟人类操作"""
        time.sleep(random.uniform(min_sec, max_sec))

    def retry_operation(self, operation, retries: int = 3, delay: float = 2.0,
                        operation_name: str = "操作"):
        """
        通用重试机制
        operation: 可调用对象，无参数
        retries: 最大重试次数
        delay: 每次重试间隔（秒）
        operation_name: 操作名称，用于日志
        返回: (成功与否, 结果或错误信息)
        """
        last_error = None
        for attempt in range(1, retries + 1):
            try:
                result = operation()
                return True, result
            except Exception as e:
                last_error = e
                if attempt < retries:
                    time.sleep(delay)
        return False, str(last_error) if last_error else "未知错误"

    def safe_page_get(self, url: str, retries: int = 2, wait_load: bool = True) -> bool:
        """
        安全地访问页面，带重试
        返回是否成功
        """
        for attempt in range(1, retries + 1):
            try:
                if not self.page:
                    return False
                self.page.get(url)
                time.sleep(1.5)
                if wait_load:
                    try:
                        self.page.wait.doc_loaded(timeout=10)
                    except:
                        pass
                time.sleep(0.5)
                return True
            except Exception as e:
                if attempt < retries:
                    time.sleep(2)
        return False

    def safe_find_element(self, selectors: List[str], timeout: int = 2, retries: int = 2):
        """
        安全地查找元素，尝试多个选择器，带重试
        selectors: 选择器列表，按优先级尝试
        返回找到的元素或None
        """
        for attempt in range(retries):
            for sel in selectors:
                try:
                    ele = self.page.ele(sel, timeout=timeout)
                    if ele:
                        return ele
                except:
                    continue
            if attempt < retries - 1:
                time.sleep(1)
        return None

    def safe_find_elements(self, selectors: List[str], timeout: int = 2, retries: int = 2):
        """
        安全地查找多个元素，尝试多个选择器，带重试
        返回元素列表或空列表
        """
        for attempt in range(retries):
            for sel in selectors:
                try:
                    eles = self.page.eles(sel)
                    if eles:
                        return eles
                except:
                    continue
            if attempt < retries - 1:
                time.sleep(1)
        return []

    def reconnect_browser(self) -> bool:
        """
        浏览器连接断开时重新连接
        返回是否成功
        """
        try:
            from app.core.browser import browser_manager
            self.page = browser_manager.connect(mode="attach")
            time.sleep(1)
            return True
        except Exception as e:
            return False

    @abstractmethod
    async def run(self):
        """执行投递主流程，子类必须实现"""
        pass

    @abstractmethod
    def check_login(self) -> bool:
        """检查登录状态，子类必须实现"""
        pass

    def get_stats(self) -> Dict[str, Any]:
        """获取统计数据和实时状态"""
        return {
            "total": self.total_count,
            "success": self.success_count,
            "failed": self.failed_count,
            "skipped": self.skipped_count,
            "current_page": self.current_page,
            "current_index": self.current_index,
            "current_total": self.current_total,
            "current_company": self.current_company,
            "current_job": self.current_job,
            "current_action": self.current_action,
            "is_paused": self._paused,
            "is_stopped": self._stopped,
        }
