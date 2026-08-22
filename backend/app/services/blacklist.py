"""黑名单服务 - 企业黑名单管理"""
from typing import List, Optional
from sqlalchemy.orm import Session
from app.models import Blacklist


class BlacklistService:
    """企业黑名单管理服务"""

    def __init__(self, db: Session):
        self.db = db

    def is_blacklisted(self, company_name: str, platform: str = "") -> bool:
        """检查企业是否在黑名单中"""
        if not company_name or len(company_name) < 2:
            return False
        query = self.db.query(Blacklist).filter(Blacklist.company_name == company_name)
        if platform:
            query = query.filter(
                (Blacklist.platform == platform) | (Blacklist.platform == "")
            )
        return query.first() is not None

    def add(self, company_name: str, platform: str = "", reason: str = "", source: str = "manual") -> bool:
        """添加企业到黑名单"""
        if not company_name or len(company_name) < 2:
            return False
        if self.is_blacklisted(company_name, platform):
            return False
        item = Blacklist(
            company_name=company_name,
            platform=platform,
            reason=reason,
            source=source
        )
        self.db.add(item)
        self.db.commit()
        return True

    def remove(self, blacklist_id: int) -> bool:
        """从黑名单移除"""
        item = self.db.query(Blacklist).filter(Blacklist.id == blacklist_id).first()
        if item:
            self.db.delete(item)
            self.db.commit()
            return True
        return False

    def list_all(self, platform: str = "", offset: int = 0, limit: int = 100) -> List[Blacklist]:
        """获取黑名单列表"""
        query = self.db.query(Blacklist)
        if platform:
            query = query.filter(Blacklist.platform == platform)
        return query.order_by(Blacklist.created_at.desc()).offset(offset).limit(limit).all()

    def count(self) -> int:
        """获取黑名单总数"""
        return self.db.query(Blacklist).count()
