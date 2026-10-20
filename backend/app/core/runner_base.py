"""平台Runner基类 - 所有平台自动化脚本继承此类"""
import asyncio
import time
import random
from abc import ABC, abstractmethod
from datetime import datetime
from pathlib import Path
from typing import Dict, Any, Optional, List
from app.core.events import event_manager
from app.schemas import RunEvent
from app.database import SessionLocal
from app.models import JobResult, Run
from app.core import observability as obs
from app.core.observability import ReasonCode, LoginState


class BaseRunner(ABC):
    """平台自动化执行器基类"""

    platform: str = "base"

    # 登录三态常量（check_login 返回值）
    LOGGED_IN = LoginState.LOGGED_IN
    NOT_LOGGED_IN = LoginState.NOT_LOGGED_IN
    LOGIN_UNKNOWN = LoginState.LOGIN_UNKNOWN
    RISK_CONTROL = LoginState.RISK_CONTROL

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
        # 阶段A 可观测：run 级失败原因/统计/日志路径
        self.cards_found = 0
        self.fail_reason = ""
        self.error_message = ""
        self.log_path = ""
        self._failure_already_recorded = False  # 单条失败是否已由 record_failure 落库
        self._list_failure_recorded = False  # 列表为空是否已记录过更具体的失败原因
        # 实时状态字段（用于批量任务监控）
        self.current_page = 0
        self.current_index = 0
        self.current_total = 0
        self.current_company = ""
        self.current_job = ""
        self.current_action = "等待中"  # 等待中/搜索中/投递中/沟通中/已完成
        self.batch_id = None  # 所属批量任务ID

    async def log(self, message: str, level: str = "info"):
        """记录日志并推送（SSE + print + 落盘到 data/logs/run_{run_id}.log）"""
        event = RunEvent(
            event_type="log",
            run_id=self.run_id,
            platform=self.platform,
            message=f"[{level.upper()}] {message}",
            data={"level": level, "batch_id": self.batch_id}
        )
        await event_manager.publish(event)
        print(f"[{self.platform}] {message}")
        # 落盘（异常静默降级，不影响主流程）
        try:
            from app.config import settings
            log_dir = Path(settings.data_dir) / "logs"
            log_dir.mkdir(parents=True, exist_ok=True)
            log_file = log_dir / f"run_{self.run_id}.log"
            line = (f"[{datetime.now().strftime('%Y-%m-%d %H:%M:%S')}] "
                    f"[{level.upper()}] {message}\n")
            with open(log_file, "a", encoding="utf-8") as f:
                f.write(line)
            # 首次写盘时回写相对路径到 Run.log_path
            if not self.log_path:
                self.log_path = f"logs/run_{self.run_id}.log"
                self._persist_run_fields(log_path=self.log_path)
        except Exception as e:
            print(f"[{self.platform}] 日志落盘失败(已降级): {e}")

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

    async def result(self, job_data: Dict[str, Any], status: str, message: str = "",
                     ai_greeting: str = "", *,
                     reason_code: str = None, error_stage: str = None,
                     error_url: str = None, screenshot_path: str = None,
                     selector_used: str = None, traceback_short: str = None):
        """推送投递结果并持久化到数据库

        新增可观测关键字参数（均默认 None，保持对旧调用 result(job, status, msg) 向后兼容）：
        reason_code/error_stage/error_url/screenshot_path/selector_used/traceback_short。
        """
        # 持久化到数据库（独立于SSE连接，确保批量模式也能保存）
        self._persist_result(job_data, status, message, ai_greeting,
                             reason_code=reason_code, error_stage=error_stage,
                             error_url=error_url, screenshot_path=screenshot_path,
                             selector_used=selector_used, traceback_short=traceback_short)

        event = RunEvent(
            event_type="result",
            run_id=self.run_id,
            platform=self.platform,
            message=message,
            data={**job_data, "status": status, "ai_greeting": ai_greeting,
                  "reason_code": reason_code or "", "batch_id": self.batch_id}
        )
        await event_manager.publish(event)

    def _persist_result(self, job_data: Dict[str, Any], status: str, message: str,
                        ai_greeting: str = "", *,
                        reason_code: str = None, error_stage: str = None,
                        error_url: str = None, screenshot_path: str = None,
                        selector_used: str = None, traceback_short: str = None):
        """将投递结果保存到数据库（同步方法，在线程中安全调用）"""
        try:
            # 失败且未显式传 reason_code 时，用消息自动归类；尽量补 error_url
            if status == "failed":
                if not reason_code:
                    reason_code = obs.classify_message(message or "")
                if not error_url:
                    error_url = obs.safe_page_url(self.page)
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
                reason_code=reason_code or "",
                error_stage=error_stage or "",
                error_url=error_url or "",
                screenshot_path=screenshot_path or "",
                selector_used=selector_used or "",
                traceback_short=traceback_short or "",
            )
            db = SessionLocal()
            try:
                db.add(record)
                db.commit()
            finally:
                db.close()
        except Exception as e:
            print(f"[{self.platform}] 保存结果失败: {e}")

    async def error(self, message: str):
        """推送错误（同时把最新错误摘要落库到 Run.error_message）"""
        try:
            self.error_message = (message or "")[:500]
            self._persist_run_fields(error_message=self.error_message)
        except Exception as e:
            print(f"[{self.platform}] error 落库失败(已降级): {e}")
        event = RunEvent(
            event_type="error",
            run_id=self.run_id,
            platform=self.platform,
            message=message,
            data={"batch_id": self.batch_id}
        )
        await event_manager.publish(event)

    async def status(self, status: str, data: Dict[str, Any] = None):
        """推送状态变更（failed 时把 reason/error 落库到 Run）"""
        if status in ("failed", "completed", "stopped"):
            self.final_status = status
        event_data = data or {}
        event_data["batch_id"] = self.batch_id
        # 落库 run 级失败字段（异常只 print，不影响 SSE）
        try:
            if status == "failed":
                # 优先用 reason_code；否则用 reason；都没有则兜底 UNKNOWN，保证每个 failed run 都有 fail_reason
                if event_data.get("reason_code"):
                    self.fail_reason = str(event_data["reason_code"])
                elif event_data.get("reason"):
                    self.fail_reason = str(event_data["reason"])
                if not self.fail_reason:
                    self.fail_reason = ReasonCode.UNKNOWN
                if event_data.get("error"):
                    self.error_message = str(event_data["error"])[:500]
                self._persist_run_fields(fail_reason=self.fail_reason,
                                         error_message=self.error_message)
        except Exception as e:
            print(f"[{self.platform}] status 落库失败(已降级): {e}")
        event = RunEvent(
            event_type="status",
            run_id=self.run_id,
            platform=self.platform,
            message=status,
            data=event_data
        )
        await event_manager.publish(event)

    def _persist_run_fields(self, fail_reason: str = None, error_message: str = None,
                            cards_found: int = None, log_path: str = None):
        """短事务更新 Run 行的可观测字段；任何异常只 print，绝不影响主流程。"""
        try:
            db = SessionLocal()
            try:
                run = db.query(Run).filter(Run.id == self.run_id).first()
                if run:
                    if fail_reason is not None:
                        run.fail_reason = fail_reason
                    if error_message is not None:
                        run.error_message = error_message
                    if cards_found is not None:
                        run.cards_found = cards_found
                    if log_path is not None:
                        run.log_path = log_path
                    db.commit()
            finally:
                db.close()
        except Exception as e:
            print(f"[{self.platform}] 落库 Run 字段失败(已降级): {e}")

    async def record_failure(self, job: Dict[str, Any], reason_code: str, stage: str,
                             selector: str = None, exc: BaseException = None,
                             message: str = None, screenshot: bool = True):
        """统一失败记录：自动取 page.url、按 reason 截图、截断堆栈、写一条 failed JobResult。

        全程 try 兜底，任何观测失败都不得影响主投递。
        调用后会置 self._failure_already_recorded=True，供 run 循环避免重复落库。
        """
        try:
            job_data = job if isinstance(job, dict) else {}
            msg = message or ""
            if exc is not None and not msg:
                msg = str(exc)
            url = obs.safe_page_url(self.page)
            shot = obs.capture_failure(self.page, self.run_id, stage, reason_code) if screenshot else ""
            tb = obs.short_traceback(exc) if exc is not None else ""
            self._persist_result(job_data, "failed", msg, "",
                                 reason_code=reason_code, error_stage=stage,
                                 error_url=url, screenshot_path=shot,
                                 selector_used=selector or "", traceback_short=tb)
            self._failure_already_recorded = True
            # 同步推一条 SSE 结果事件
            try:
                event = RunEvent(
                    event_type="result",
                    run_id=self.run_id,
                    platform=self.platform,
                    message=msg,
                    data={**job_data, "status": "failed", "reason_code": reason_code,
                          "screenshot_path": shot, "batch_id": self.batch_id}
                )
                await event_manager.publish(event)
            except Exception as e:
                print(f"[{self.platform}] record_failure SSE 失败(已降级): {e}")
        except Exception as e:
            print(f"[{self.platform}] record_failure 失败(已降级): {e}")

    async def record_list_empty(self, url: str, stage: str = "list"):
        """记录列表为空：reason_code=LIST_EMPTY, cards_found=0, 截图+URL+风控特征。

        若 _get_job_list 已记录过更具体的失败原因（如 CARD_SELECTOR_FAIL），
        则只置 cards_found=0，不再重复落库。
        """
        try:
            self.cards_found = 0
            self._persist_run_fields(cards_found=0)
            if self._list_failure_recorded:
                # 更具体的失败原因已记录，避免重复落库
                return
            url = url or obs.safe_page_url(self.page)
            shot = obs.capture_failure(self.page, self.run_id, stage, ReasonCode.LIST_EMPTY)
            risk_hit = ""
            try:
                hit, feat = obs.detect_risk_control(self.page)
                if hit:
                    risk_hit = feat
            except Exception:
                risk_hit = ""
            job_data = {"title": "(列表为空)", "company": self.platform, "job_url": url}
            msg = f"列表为空，cards_found=0"
            if risk_hit:
                msg += f"，命中风控特征:{risk_hit}"
            self._persist_result(job_data, "failed", msg, "",
                                 reason_code=ReasonCode.LIST_EMPTY, error_stage=stage,
                                 error_url=url, screenshot_path=shot,
                                 selector_used="", traceback_short=risk_hit)
            try:
                event = RunEvent(
                    event_type="result",
                    run_id=self.run_id,
                    platform=self.platform,
                    message=msg,
                    data={**job_data, "status": "failed", "reason_code": ReasonCode.LIST_EMPTY,
                          "screenshot_path": shot, "batch_id": self.batch_id}
                )
                await event_manager.publish(event)
            except Exception:
                pass
        except Exception as e:
            print(f"[{self.platform}] record_list_empty 失败(已降级): {e}")

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
    def check_login(self) -> str:
        """检查登录状态，子类必须实现。

        返回登录三态字符串（见 LoginState / BaseRunner 常量）：
        - logged_in
        - not_logged_in
        - unknown（检测不到，不再默认 True）
        - risk_control（命中风控/安全验证页，只检测不绕过）
        """
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
