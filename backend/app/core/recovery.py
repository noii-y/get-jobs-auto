# -*- coding: utf-8 -*-
"""启动自愈：把上次异常退出遗留的"僵尸 running"任务置为 failed。

原则：只更新状态字段（status / finished_at），绝不删除任何投递记录。
"""
from datetime import datetime
from typing import Dict, List

from app.database import SessionLocal
from app.models import Run, BatchJob


def recover_zombies() -> Dict[str, List[int]]:
    """重置所有僵尸任务，返回被重置的 id 列表。"""
    db = SessionLocal()
    reset_runs: List[int] = []
    reset_batches: List[int] = []
    try:
        now = datetime.now()

        zombies = (
            db.query(Run)
            .filter(Run.status == "running", Run.finished_at.is_(None))
            .all()
        )
        for r in zombies:
            r.status = "failed"
            r.finished_at = now
            reset_runs.append(r.id)

        batch_zombies = (
            db.query(BatchJob)
            .filter(BatchJob.status == "running")
            .all()
        )
        for b in batch_zombies:
            b.status = "failed"
            if b.finished_at is None:
                b.finished_at = now
            reset_batches.append(b.id)

        db.commit()
    except Exception:
        db.rollback()
        raise
    finally:
        db.close()
    return {"run_ids": reset_runs, "batch_ids": reset_batches}
