"""通知服务 - 企业微信消息推送"""
from typing import Optional
import httpx


class NotifyService:
    """企业微信机器人通知服务"""

    def __init__(self):
        self.webhook_url = ""
        self.enabled = False
        self.notify_start = True
        self.notify_finish = True
        self.notify_error = True

    def configure(self, webhook_url: str, enabled: bool,
                  notify_start: bool = True, notify_finish: bool = True, notify_error: bool = True):
        """配置通知服务"""
        self.webhook_url = webhook_url
        self.enabled = enabled and bool(webhook_url)
        self.notify_start = notify_start
        self.notify_finish = notify_finish
        self.notify_error = notify_error

    async def send_message(self, content: str) -> bool:
        """发送文本消息"""
        if not self.enabled or not self.webhook_url:
            return False

        try:
            async with httpx.AsyncClient(timeout=10.0) as client:
                response = await client.post(
                    self.webhook_url,
                    json={
                        "msgtype": "text",
                        "text": {"content": content}
                    }
                )
                response.raise_for_status()
                return True
        except Exception as e:
            print(f"[Notify] 发送消息失败: {e}")
            return False

    async def send_markdown(self, content: str) -> bool:
        """发送Markdown消息"""
        if not self.enabled or not self.webhook_url:
            return False

        try:
            async with httpx.AsyncClient(timeout=10.0) as client:
                response = await client.post(
                    self.webhook_url,
                    json={
                        "msgtype": "markdown",
                        "markdown": {"content": content}
                    }
                )
                response.raise_for_status()
                return True
        except Exception as e:
            print(f"[Notify] 发送Markdown失败: {e}")
            return False

    async def notify_task_start(self, platform: str, config: dict):
        """任务开始通知"""
        if not self.notify_start:
            return
        keyword = config.get("keyword", "未设置")
        city = config.get("city", "未设置")
        await self.send_markdown(
            f"### 🚀 投递任务已启动\n\n"
            f"**平台**: {platform}\n"
            f"**关键词**: {keyword}\n"
            f"**城市**: {city}\n"
            f"**时间**: {self._now_str()}"
        )

    async def notify_task_finish(self, platform: str, stats: dict):
        """任务完成通知"""
        if not self.notify_finish:
            return
        await self.send_markdown(
            f"### ✅ 投递任务已完成\n\n"
            f"**平台**: {platform}\n"
            f"**总计**: {stats.get('total', 0)}\n"
            f"**成功**: {stats.get('success', 0)}\n"
            f"**失败**: {stats.get('failed', 0)}\n"
            f"**跳过**: {stats.get('skipped', 0)}\n"
            f"**时间**: {self._now_str()}"
        )

    async def notify_error(self, platform: str, error_msg: str):
        """错误通知"""
        if not self.notify_error:
            return
        await self.send_markdown(
            f"### ❌ 投递任务异常\n\n"
            f"**平台**: {platform}\n"
            f"**错误**: {error_msg}\n"
            f"**时间**: {self._now_str()}"
        )

    @staticmethod
    def _now_str() -> str:
        from datetime import datetime
        return datetime.now().strftime("%Y-%m-%d %H:%M:%S")


# 全局通知服务实例
notify_service = NotifyService()
