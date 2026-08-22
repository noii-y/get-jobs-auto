"""SSE事件管理器 - 管理运行事件的发布与订阅"""
import asyncio
import json
from datetime import datetime
from typing import Dict, Set, Optional
from app.schemas import RunEvent


class EventManager:
    """事件管理器，支持按run_id订阅"""

    def __init__(self):
        self._subscribers: Dict[int, Set[asyncio.Queue]] = {}
        self._global_subscribers: Set[asyncio.Queue] = set()
        self._event_history: Dict[int, list] = {}  # 历史事件，用于重连

    def create_queue(self) -> asyncio.Queue:
        """创建一个新的订阅队列"""
        return asyncio.Queue(maxsize=1000)

    def subscribe(self, run_id: Optional[int] = None) -> asyncio.Queue:
        """订阅事件，run_id为None时订阅全局事件"""
        queue = self.create_queue()
        if run_id is None:
            self._global_subscribers.add(queue)
        else:
            if run_id not in self._subscribers:
                self._subscribers[run_id] = set()
            self._subscribers[run_id].add(queue)
            # 推送历史事件
            if run_id in self._event_history:
                for event in self._event_history[run_id]:
                    queue.put_nowait(event)
        return queue

    def unsubscribe(self, queue: asyncio.Queue, run_id: Optional[int] = None):
        """取消订阅"""
        if run_id is None:
            self._global_subscribers.discard(queue)
        elif run_id in self._subscribers:
            self._subscribers[run_id].discard(queue)

    async def publish(self, event: RunEvent):
        """发布事件"""
        event_dict = event.model_dump(mode="json")
        event_json = json.dumps(event_dict, ensure_ascii=False, default=str)

        # 保存历史
        if event.run_id:
            if event.run_id not in self._event_history:
                self._event_history[event.run_id] = []
            self._event_history[event.run_id].append(event_json)
            # 最多保留500条
            if len(self._event_history[event.run_id]) > 500:
                self._event_history[event.run_id] = self._event_history[event.run_id][-500:]

        # 推送给全局订阅者
        for queue in list(self._global_subscribers):
            try:
                queue.put_nowait(event_json)
            except asyncio.QueueFull:
                pass

        # 推送给特定run_id订阅者
        if event.run_id and event.run_id in self._subscribers:
            for queue in list(self._subscribers[event.run_id]):
                try:
                    queue.put_nowait(event_json)
                except asyncio.QueueFull:
                    pass

        # 如果事件数据中包含 batch_id，同时推送给批量任务订阅者
        batch_id = event.data.get("batch_id") if event.data else None
        if batch_id and batch_id != event.run_id and batch_id in self._subscribers:
            for queue in list(self._subscribers[batch_id]):
                try:
                    queue.put_nowait(event_json)
                except asyncio.QueueFull:
                    pass

    def publish_sync(self, event: RunEvent):
        """同步发布事件（在非async上下文中使用）"""
        try:
            loop = asyncio.get_event_loop()
            if loop.is_running():
                asyncio.ensure_future(self.publish(event))
        except RuntimeError:
            pass

    def clear_history(self, run_id: int):
        """清除指定run的历史事件"""
        self._event_history.pop(run_id, None)
        self._subscribers.pop(run_id, None)


# 全局事件管理器实例
event_manager = EventManager()
